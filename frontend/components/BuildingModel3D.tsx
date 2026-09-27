"use client";

import { Component, Suspense, useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import dynamic from "next/dynamic";
import { Canvas, type ThreeEvent } from "@react-three/fiber";
import { Bounds, OrbitControls, useGLTF } from "@react-three/drei";
import { Box3, Color, DoubleSide, Mesh, ShaderMaterial, Vector3 } from "three";
import { api } from "@/lib/api";
import type { Building, BuildingModel, Evidence } from "@/lib/types";

const MAX_HEAT_SCORE = 10;
const ESTIMATED_FLOOR_HEIGHT_METERS = 3;
const HEAT_LOW = new Color("#f0d79f");
const HEAT_MID = new Color("#e16d3e");
const HEAT_HIGH = new Color("#a61f1f");

type FloorHeat = {
  floor: number;
  count: number;
  score: number;
  color: string;
  records: Evidence[];
};

function heatColor(score: number) {
  const clamped = Math.max(0, Math.min(MAX_HEAT_SCORE, score));
  const color = clamped <= 5
    ? HEAT_LOW.clone().lerp(HEAT_MID, clamped / 5)
    : HEAT_MID.clone().lerp(HEAT_HIGH, (clamped - 5) / 5);
  return `#${color.getHexString()}`;
}

function floorHeatFor(records: Evidence[]): FloorHeat[] {
  const grouped = new Map<number, Evidence[]>();
  records.forEach((record) => {
    if (record.floor === null || record.floor <= 0) return;
    const floorRecords = grouped.get(record.floor) ?? [];
    floorRecords.push(record);
    grouped.set(record.floor, floorRecords);
  });

  return Array.from(grouped, ([floor, floorRecords]) => {
    const count = floorRecords.length;
    const score = Math.min(MAX_HEAT_SCORE, count);
    return { floor, count, score, color: heatColor(score), records: floorRecords };
  }).sort((a, b) => a.floor - b.floor);
}

const PhotorealisticBuildingView = dynamic(
  () => import("./PhotorealisticBuildingView").then((module) => module.PhotorealisticBuildingView),
  {
    ssr: false,
    loading: () => <div className="model-loading" role="status">Loading geographic viewer…</div>,
  },
);

function hasValidCoordinates(building: Building): building is Building & { latitude: number; longitude: number } {
  return typeof building.latitude === "number"
    && Number.isFinite(building.latitude)
    && building.latitude >= -90
    && building.latitude <= 90
    && typeof building.longitude === "number"
    && Number.isFinite(building.longitude)
    && building.longitude >= -180
    && building.longitude <= 180;
}

function IsolatedModel({
  url,
  floorHeat,
  onSelect,
}: {
  url: string;
  floorHeat: FloorHeat[];
  onSelect: (record: Evidence) => void;
}) {
  const { scene } = useGLTF(url);
  const model = useMemo(() => scene.clone(true), [scene]);
  const placement = useMemo(() => {
    const bounds = new Box3().setFromObject(model);
    const size = bounds.getSize(new Vector3());
    const center = bounds.getCenter(new Vector3());
    const highestDocumentedFloor = Math.max(1, ...floorHeat.map((item) => item.floor));
    const estimatedFloorCount = Math.max(
      highestDocumentedFloor,
      Math.max(1, Math.round(size.y / ESTIMATED_FLOOR_HEIGHT_METERS)),
    );
    return { bounds, size, center, estimatedFloorCount };
  }, [floorHeat, model]);
  const floorHeight = placement.size.y / placement.estimatedFloorCount;
  const heatLayers = useMemo(() => floorHeat.map((item) => {
    const layer = model.clone(true);
    const bottom = placement.bounds.min.y - placement.center.y + ((item.floor - 1) * floorHeight);
    const top = bottom + (floorHeight * 0.82);
    const materials: ShaderMaterial[] = [];

    layer.traverse((object) => {
      if (!(object instanceof Mesh)) return;
      const material = new ShaderMaterial({
        uniforms: {
          heatColor: { value: new Color(item.color) },
          heatOpacity: { value: 0.68 + ((item.score / MAX_HEAT_SCORE) * 0.24) },
          heatBottom: { value: bottom },
          heatTop: { value: top },
        },
        vertexShader: `
          varying float modelY;
          void main() {
            vec4 worldPosition = modelMatrix * vec4(position, 1.0);
            modelY = worldPosition.y;
            gl_Position = projectionMatrix * viewMatrix * worldPosition;
          }
        `,
        fragmentShader: `
          uniform vec3 heatColor;
          uniform float heatOpacity;
          uniform float heatBottom;
          uniform float heatTop;
          varying float modelY;
          void main() {
            if (modelY < heatBottom || modelY > heatTop) discard;
            gl_FragColor = vec4(heatColor, heatOpacity);
          }
        `,
        transparent: true,
        side: DoubleSide,
        depthTest: true,
        depthWrite: false,
        polygonOffset: true,
        polygonOffsetFactor: -2,
        polygonOffsetUnits: -2,
      });
      object.material = material;
      object.renderOrder = 10;
      materials.push(material);
    });

    return { ...item, layer, materials };
  }), [floorHeat, floorHeight, model, placement.bounds.min.y, placement.center.y]);

  useEffect(() => () => {
    heatLayers.forEach((layer) => layer.materials.forEach((material) => material.dispose()));
  }, [heatLayers]);

  return (
    <group position={[-placement.center.x, -placement.center.y, -placement.center.z]}>
      <primitive object={model} dispose={null} />
      {heatLayers.map((item) => <primitive
        key={item.floor}
        object={item.layer}
        dispose={null}
        onClick={(event: ThreeEvent<MouseEvent>) => {
          event.stopPropagation();
          onSelect(item.records[0]);
        }}
      />)}
    </group>
  );
}

class ModelErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed
      ? <div className="model-loading model-error" role="alert">The building model could not be opened. Use reset to retry.</div>
      : this.props.children;
  }
}

type Props = { building: Building; records: Evidence[]; onSelect: (record: Evidence) => void };

export function BuildingModel3D(props: Props) {
  return <BuildingViewer key={props.building.id} {...props} />;
}

function BuildingViewer({
  building,
  records,
  onSelect,
}: Props) {
  const [view, setView] = useState<"analysis" | "real">("analysis");
  const [model, setModel] = useState<BuildingModel | null>(null);
  const [error, setError] = useState("");
  const [analysisKey, setAnalysisKey] = useState(0);
  const [realResetKey, setRealResetKey] = useState(0);
  useEffect(() => {
    let cancelled = false;
    api.model(building.id).then((result) => {
      if (!cancelled) setModel(result);
    }).catch(() => {
      if (!cancelled) setError("The building model is temporarily unavailable.");
    });
    return () => { cancelled = true; };
  }, [building.id, analysisKey]);
  const located = useMemo(
    () => records.filter((record) => record.floor !== null && record.floor > 0),
    [records],
  );
  const floorHeat = useMemo(() => floorHeatFor(records), [records]);
  const unlocatedCount = records.length - located.length;
  const realWorldAvailable = !building.demo && hasValidCoordinates(building);

  function resetView() {
    if (view === "real") {
      setRealResetKey((value) => value + 1);
      return;
    }
    if (model?.status === "ready") useGLTF.clear(model.url);
    setModel(null);
    setError("");
    setAnalysisKey((value) => value + 1);
  }

  return (
    <section className="building-model-card" aria-labelledby="building-model-title">
      <div className="model-card-head">
        <div>
          <div className="eyebrow">{building.demo ? "Single-building example" : "Selected building"}</div>
          <h2 id="building-model-title">Building in 3D</h2>
        </div>
        <div className="model-controls">
          {view === "analysis" && model?.status === "ready" && <a className="model-download" href={model.download_url} download title="Download isolated Rhino geometry">↓ .3dm</a>}
          <button onClick={resetView} aria-label={`Reset ${view === "analysis" ? "building analysis" : "real-world"} view`} title="Reset view">↺</button>
        </div>
      </div>

      <div className="model-view-tabs" role="tablist" aria-label="3D view">
        <button type="button" role="tab" aria-selected={view === "analysis"} onClick={() => setView("analysis")}>Building analysis</button>
        <button
          type="button"
          role="tab"
          aria-selected={view === "real"}
          disabled={!realWorldAvailable}
          title={building.demo ? "Unavailable for fictional demo addresses" : !realWorldAvailable ? "Valid coordinates are required" : undefined}
          onClick={() => setView("real")}
        >
          Real-world view
        </button>
      </div>

      <div className={`model-stage model-stage-webgl${view === "analysis" && (model?.status === "unavailable" || error) ? " model-stage-unavailable" : ""}`}>
        {view === "analysis" ? <>
          {model?.status === "ready" && !error ? <ModelErrorBoundary key={analysisKey}>
          <Suspense fallback={<div className="model-loading" role="status">Loading building geometry…</div>}>
          <Canvas
            camera={{ position: [30, 24, 36], fov: 38, near: 0.01, far: 10_000 }}
            dpr={[1, 2]}
            gl={{ antialias: true, alpha: true }}
          >
            <color attach="background" args={["#edf2ee"]} />
            <ambientLight intensity={0.8} />
            <directionalLight position={[6, 10, 8]} intensity={2} />
            <directionalLight position={[-7, 3, -5]} intensity={0.5} />
              <Bounds fit clip observe margin={1.2}>
                <IsolatedModel url={model.url} floorHeat={floorHeat} onSelect={onSelect} />
              </Bounds>
            <OrbitControls makeDefault enableDamping dampingFactor={0.08} minDistance={0.4} maxDistance={10_000} />
          </Canvas>
          </Suspense>
          {floorHeat.length > 0 && <div className="model-heat-legend" aria-label="Universal floor heat scale from zero to ten records">
            <strong>Floor heat</strong>
            <span className="model-heat-scale" aria-hidden="true" />
            <span className="model-heat-scale-labels"><span>0</span><span>5</span><span>10+</span></span>
            <small>records per floor</small>
          </div>}
          <div className="model-drag-hint">Drag to rotate · scroll to zoom · right-drag to pan</div>
          </ModelErrorBoundary> : <div className="model-loading" role="status">
            {model?.status === "unavailable" && !error ? <div className="model-unavailable-copy">
              <strong>{model.reason === "missing_district" ? "District model needed" : "Building model unavailable"}</strong>
              <p>{model.message}</p>
            </div> : error || "Isolating building geometry…"}
          </div>}
        </> : realWorldAvailable && <PhotorealisticBuildingView
          address={building.address}
          latitude={building.latitude}
          longitude={building.longitude}
          resetKey={realResetKey}
          onReturn={() => setView("analysis")}
        />}
      </div>

      {view === "real" && realWorldAvailable && <p className="photo-interaction-hint">Left-drag to pan · Ctrl/middle-drag to rotate · scroll or right-drag to zoom · ↺ returns to the address</p>}
      {!realWorldAvailable && <p className="photo-unavailable-note">
        {building.demo
          ? "Real-world view is unavailable for fictional demo addresses so the scene cannot be mistaken for demo records."
          : "Real-world view requires verified latitude and longitude for this address."}
      </p>}

      {floorHeat.length > 0 && <div className="model-records" aria-label="Documented record heat by floor">
        <span>Floor record heat</span>
        <div>
          {floorHeat.map((item) => (
            <button
              key={item.floor}
              className="model-record-marker"
              style={{ "--heat-color": item.color } as CSSProperties}
              onClick={() => onSelect(item.records[0])}
              title={`Floor ${item.floor}: ${item.count} documented record${item.count === 1 ? "" : "s"} · ${item.score}/10 fixed heat scale`}
            >
              <span>F{item.floor}</span><strong>{item.count}</strong>
            </button>
          ))}
        </div>
      </div>}

      <div className="model-summary">
        <div><strong>{located.length}</strong><span>floor-specific records</span></div>
        <div><strong>{unlocatedCount}</strong><span>location not specified</span></div>
      </div>
      {view === "analysis" && model?.status === "ready" && <p className="model-disclaimer">
        {model.message} Heat bands use a fixed 0–10 record scale and estimated floor positions; 10+ is always the maximum. Floor buttons open documented records.
      </p>}
      {view === "real" && <p className="model-disclaimer">Google imagery is visual context only. The address marker comes from the report&apos;s independent building coordinates; incident records are not assigned to visible windows or apartments.</p>}
      <span className="sr-only">3D model context for {building.address}</span>
    </section>
  );
}
