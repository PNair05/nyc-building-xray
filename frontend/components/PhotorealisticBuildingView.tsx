"use client";

import { useEffect, useRef, useState } from "react";
import type { Viewer } from "cesium";

type Status =
  | { kind: "loading"; message: string }
  | { kind: "ready"; message: string }
  | { kind: "error"; message: string };

type Props = {
  address: string;
  latitude: number;
  longitude: number;
  resetKey: number;
  onReturn: () => void;
};

function explainTileFailure(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  const normalized = message.toLowerCase();

  if (normalized.includes("401") || normalized.includes("403") || normalized.includes("api key") || normalized.includes("referer")) {
    return "Google Maps could not authorize this website. Check the key's Map Tiles API and website restrictions.";
  }
  if (normalized.includes("429") || normalized.includes("quota") || normalized.includes("resource_exhausted")) {
    return "The Google Map Tiles quota is currently exhausted. Try again after the quota resets.";
  }
  if (normalized.includes("404") || normalized.includes("not found") || normalized.includes("coverage")) {
    return "Photorealistic coverage is not available for this location.";
  }
  if (normalized.includes("network") || normalized.includes("fetch") || normalized.includes("load")) {
    return "The photorealistic scene could not be downloaded. Check the network connection and try again.";
  }
  return "The photorealistic scene could not be opened. Return to Building analysis or try again.";
}

export function PhotorealisticBuildingView({ address, latitude, longitude, resetKey, onReturn }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const resetCameraRef = useRef<() => void>(() => undefined);
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY?.trim();
  const [status, setStatus] = useState<Status>(() => apiKey
    ? { kind: "loading", message: "Preparing the real-world scene…" }
    : {
        kind: "error",
        message: "Real-world view is not configured. Add NEXT_PUBLIC_GOOGLE_MAPS_API_KEY to frontend/.env.local.",
      });

  useEffect(() => {
    if (!apiKey) return;
    if (!containerRef.current) return;
    if (!("WebGLRenderingContext" in window)) {
      queueMicrotask(() => setStatus({ kind: "error", message: "This browser does not support WebGL, which the real-world view requires." }));
      return;
    }

    let cancelled = false;
    let removeInitialTilesListener: (() => void) | undefined;
    let removeTileFailureListener: (() => void) | undefined;

    async function initialize() {
      try {
        (window as typeof window & { CESIUM_BASE_URL: string }).CESIUM_BASE_URL = "/cesium/";
        const Cesium = await import("cesium");
        if (cancelled || !containerRef.current) return;

        Cesium.RequestScheduler.requestsByServer["tile.googleapis.com:443"] = 18;
        const viewer = new Cesium.Viewer(containerRef.current, {
          animation: false,
          baseLayer: false,
          baseLayerPicker: false,
          fullscreenButton: false,
          geocoder: false,
          globe: false,
          homeButton: false,
          infoBox: false,
          navigationHelpButton: false,
          projectionPicker: false,
          requestRenderMode: true,
          sceneModePicker: false,
          selectionIndicator: false,
          shouldAnimate: false,
          timeline: false,
          vrButton: false,
        });
        if (cancelled) {
          viewer.destroy();
          return;
        }
        viewerRef.current = viewer;
        viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#dbe7e8");
        viewer.scene.screenSpaceCameraController.enableCollisionDetection = true;

        let targetHeight = 0;
        const positionCamera = () => {
          const target = Cesium.Cartesian3.fromDegrees(longitude, latitude, targetHeight + 12);
          viewer.camera.lookAt(target, new Cesium.HeadingPitchRange(0, -0.55, 220));
          viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
          viewer.scene.requestRender();
        };
        resetCameraRef.current = positionCamera;
        positionCamera();

        const marker = viewer.entities.add({
          name: `${address} address location`,
          position: Cesium.Cartesian3.fromDegrees(longitude, latitude, 12),
          point: {
            color: Cesium.Color.fromCssColorString("#c27b25"),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 3,
            pixelSize: 13,
          },
          label: {
            backgroundColor: Cesium.Color.fromCssColorString("#0b2837").withAlpha(0.9),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            fillColor: Cesium.Color.WHITE,
            font: "600 13px system-ui",
            outlineColor: Cesium.Color.fromCssColorString("#0b2837"),
            outlineWidth: 3,
            pixelOffset: new Cesium.Cartesian2(0, -20),
            showBackground: true,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            text: "Address location",
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          },
        });

        const rootUrl = `https://tile.googleapis.com/v1/3dtiles/root.json?key=${encodeURIComponent(apiKey!)}`;
        const tileset = await Cesium.Cesium3DTileset.fromUrl(rootUrl, {
          maximumScreenSpaceError: 16,
          showCreditsOnScreen: true,
          skipLevelOfDetail: true,
        });
        if (cancelled) {
          tileset.destroy();
          return;
        }
        viewer.scene.primitives.add(tileset);

        removeTileFailureListener = tileset.tileFailed.addEventListener((failure: { message?: string }) => {
          if (!cancelled) setStatus({ kind: "error", message: explainTileFailure(failure.message || "Tile load failed") });
        });

        removeInitialTilesListener = tileset.initialTilesLoaded.addEventListener(async () => {
          if (cancelled) return;
          try {
            if (viewer.scene.sampleHeightSupported) {
              const [sampled] = await viewer.scene.sampleHeightMostDetailed([
                Cesium.Cartographic.fromDegrees(longitude, latitude),
              ]);
              if (sampled && Number.isFinite(sampled.height)) targetHeight = sampled.height;
            }
          } catch {
            // Keep the ellipsoid-height fallback when scene depth sampling is unavailable.
          }
          if (cancelled) return;
          marker.position = new Cesium.ConstantPositionProperty(
            Cesium.Cartesian3.fromDegrees(longitude, latitude, targetHeight + 12),
          );
          positionCamera();
          setStatus({ kind: "ready", message: "Real-world scene ready" });
        });
        viewer.scene.requestRender();
      } catch (error) {
        if (!cancelled) setStatus({ kind: "error", message: explainTileFailure(error) });
      }
    }

    void initialize();
    return () => {
      cancelled = true;
      removeInitialTilesListener?.();
      removeTileFailureListener?.();
      resetCameraRef.current = () => undefined;
      const viewer = viewerRef.current;
      viewerRef.current = null;
      if (viewer && !viewer.isDestroyed()) viewer.destroy();
    };
  }, [address, apiKey, latitude, longitude]);

  useEffect(() => {
    if (resetKey > 0) resetCameraRef.current();
  }, [resetKey]);

  return (
    <>
      <div ref={containerRef} className="photorealistic-canvas" aria-label={`Photorealistic 3D map centered on ${address}`} />
      <div className="photorealistic-source-note">Google photorealistic scene · NYC address marker</div>
      {status.kind !== "ready" && <div className={`photo-status photo-status-${status.kind}`} role={status.kind === "error" ? "alert" : "status"}>
        <strong>{status.kind === "error" ? "Real-world view unavailable" : "Loading real-world view"}</strong>
        <p>{status.message}</p>
        {status.kind === "error" && <button type="button" onClick={onReturn}>Return to Building analysis</button>}
      </div>}
    </>
  );
}
