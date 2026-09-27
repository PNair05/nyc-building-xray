"""Extract one footprint from the original DCP model, without mesh decimation.

DCP's unjoined building components have no BIN/address identifiers. Live matches
therefore require a unique footprint containing the geocoded address point.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import threading
from pathlib import Path

import httpx
import numpy as np
import rhino3dm
from pyproj import Transformer
from shapely import MultiLineString, MultiPoint, Point, Polygon, build_area, constrained_delaunay_triangles

from app.models import Building
from app.storage.cache import get_cache, set_cache

MODEL_DIR = Path(__file__).resolve().parents[3] / "frontend/public/models"
OUTPUT_DIR = MODEL_DIR / "buildings"
INDEX_PATH = OUTPUT_DIR / "index.json"
VERSION = 2
BOROUGHS = {"BK": "Brooklyn", "BX": "Bronx", "MN": "Manhattan", "QN": "Queens", "SI": "Staten Island"}
# Original NYC State Plane feet coordinates were converted to Rhino millimeters.
MM_PER_FOOT = 304.8
TO_STATE_PLANE = Transformer.from_crs(4326, 2263, always_xy=True)
EXTRACTION_LOCK = threading.Lock()
PLUTO_URL = "https://data.cityofnewyork.us/resource/64uk-42ks.json"


def community_district(building: Building) -> str | None:
    """Use the tax lot only to resolve coverage, never to select a building mesh."""
    if not building.bbl or len(building.bbl) != 10 or not building.bbl.isdigit():
        return None
    key = f"model-district:{building.bbl}"
    cached = get_cache(key, ttl_seconds=86400)
    if cached:
        return cached.get("district")
    try:
        response = httpx.get(PLUTO_URL, params={"bbl": building.bbl, "$select": "bbl,cd", "$limit": "2"}, timeout=8)
        response.raise_for_status()
        rows = response.json()
        values = {int(float(row["cd"])) for row in rows}
        if len(values) != 1:
            return None
        cd = values.pop()
        prefix = {1: "MN", 2: "BX", 3: "BK", 4: "QN", 5: "SI"}.get(cd // 100)
        if not prefix or not 1 <= cd % 100 <= 18:
            return None
        code = f"{prefix}{cd % 100:02}"
        set_cache(key, {"district": code})
        return code
    except (httpx.HTTPError, ValueError, KeyError, TypeError, OverflowError):
        return None


def unmatched_model(building: Building, catalog: dict) -> dict:
    district = community_district(building)
    available = [d["code"] for d in catalog.get("districts", [])
                 if (MODEL_DIR / d["file"]).exists() and source_stamp(MODEL_DIR / d["file"]) == d["stamp"]]
    result = {"status": "unavailable", "reason": "footprint_unmatched", "available_districts": available,
              "message": "The address location could not be matched to one building footprint in the available models."}
    if not district:
        return result
    filename = f"NYC_3DModel_{district}.3dm"
    result.update(required_district=district, required_file=filename)
    if not (MODEL_DIR / filename).exists():
        result.update(reason="missing_district", message=f"This address is in {building.borough} Community District {int(district[2:])}. Its 3D model is not installed yet.")
    elif district not in available:
        result.update(reason="index_outdated", message=f"The model for {building.borough} Community District {int(district[2:])} needs to be prepared before this building can be shown.")
    return result


def source_stamp(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def layer_roles(source: rhino3dm.File3dm) -> dict[int, int]:
    names = {"buildingfootprint": 3, "buildingrooftop": 4, "buildingfacade": 5,
             "surfacefootprint": 6, "surfacerooftop": 7, "surfacefacade": 8,
             "buildingfootprintsurface": 6, "buildingrooftopsurface": 7, "buildingfacadesurface": 8}
    return {layer.Index: names[name] for layer in source.Layers
            if (name := layer.Name.lower().replace("_", "").replace(" ", "")) in names}


def footprint_rows(source: rhino3dm.File3dm) -> list[dict]:
    rows = []
    roles = layer_roles(source)
    scale = rhino3dm.UnitSystem.UnitScale(source.Settings.ModelUnitSystem, rhino3dm.UnitSystem.Millimeters)
    for index, obj in enumerate(source.Objects):
        if roles.get(obj.Attributes.LayerIndex) != 3 or not isinstance(obj.Geometry, rhino3dm.Curve):
            continue
        line = obj.Geometry.TryGetPolyline()
        if line is None or not line.IsClosed:
            continue
        points = [[p.X, p.Y] for p in line]
        polygon = Polygon(points)
        if not polygon.is_valid or polygon.area * scale * scale < 1_000_000:
            continue
        rows.append({"index": index, "points": points, "bounds": list(polygon.bounds)})
    return rows


def select_footprint(rows: list[dict], x: float, y: float) -> dict | None:
    point = Point(x, y)
    matches = []
    for row in rows:
        left, bottom, right, top = row["bounds"]
        if left <= x <= right and bottom <= y <= top and Polygon(row["points"]).covers(point):
            matches.append(row)
    # Shared boundaries and overlapping footprints need confirmation, not a guess.
    return matches[0] if len(matches) == 1 else None


def geometry_points(geometry) -> list[tuple[float, float, float]]:
    if isinstance(geometry, rhino3dm.Brep):
        return [(v.Location.X, v.Location.Y, v.Location.Z) for v in geometry.Vertices]
    if isinstance(geometry, rhino3dm.Curve):
        polyline = geometry.TryGetPolyline()
        if polyline is not None:
            return [(p.X, p.Y, p.Z) for p in polyline]
    return []


def triangulate_outline(points: list[tuple[float, float, float]]) -> list[list[float]]:
    """Triangulate a planar boundary in its own plane, retaining every corner."""
    vertices = np.asarray(points, dtype=float)
    if len(vertices) < 4 or not np.allclose(vertices[0], vertices[-1], rtol=0, atol=0.01):
        raise ValueError("Building boundary is not a closed polygon")
    vertices = vertices[:-1]
    origin = vertices[0]
    edges = vertices - origin
    first = next((edge for edge in edges if np.linalg.norm(edge) > 0.01), None)
    if first is None:
        return []
    u = first / np.linalg.norm(first)
    normal = next((np.cross(u, edge) for edge in edges if np.linalg.norm(np.cross(u, edge)) > 0.01), None)
    if normal is None:
        return []
    normal /= np.linalg.norm(normal)
    v = np.cross(normal, u)
    if np.max(np.abs(edges @ normal)) > 1:
        raise ValueError("Non-planar boundary requires a dedicated surface tessellator")
    polygon = Polygon(np.column_stack((edges @ u, edges @ v)))
    if not polygon.is_valid:
        raise ValueError("Invalid building boundary")
    triangles = []
    for triangle in constrained_delaunay_triangles(polygon).geoms:
        for x, y in list(triangle.exterior.coords)[:3]:
            triangles.append((origin + x * u + y * v).tolist())
    return triangles


def triangulate_surface(face: rhino3dm.Brep, scale: float) -> list[list[float]]:
    """Use the actual surface boundary, including interior loops and roof holes."""
    boundaries = []
    for edge in face.Edges:
        line = edge.TryGetPolyline()
        if line is None:
            raise ValueError("Curved surface requires a dedicated surface tessellator")
        boundaries.append(np.asarray([(p.X * scale, p.Y * scale, p.Z * scale) for p in line]))
    vertices = np.concatenate(boundaries)
    origin = vertices[0]
    offsets = vertices - origin
    first = next((p for p in offsets if np.linalg.norm(p) > 0.01), None)
    if first is None:
        return []
    u = first / np.linalg.norm(first)
    normal = next((np.cross(u, p) for p in offsets if np.linalg.norm(np.cross(u, p)) > 0.01), None)
    if normal is None:
        return []
    normal /= np.linalg.norm(normal)
    v = np.cross(normal, u)
    if np.max(np.abs(offsets @ normal)) > 1:
        raise ValueError("Non-planar surface requires a dedicated surface tessellator")
    segments = [np.column_stack(((boundary - origin) @ u, (boundary - origin) @ v)) for boundary in boundaries]
    area = build_area(MultiLineString(segments))
    if area.is_empty or not area.is_valid:
        raise ValueError("Surface boundary could not be reconstructed")
    return [(origin + x * u + y * v).tolist()
            for triangle in constrained_delaunay_triangles(area).geoms
            for x, y in list(triangle.exterior.coords)[:3]]


def boundary_key(points: list[tuple[float, float, float]], scale: float) -> frozenset:
    return frozenset(tuple(round(n * scale, 3) for n in point) for point in points)


def write_glb(path: Path, triangles: list[list[float]], origin: list[float]) -> int:
    points = (np.asarray(triangles, dtype=float) - np.asarray(origin)) / 1000
    # Rhino Z-up to glTF Y-up, in meters, rebased before float32 conversion.
    points = np.column_stack((points[:, 0], points[:, 2], -points[:, 1])).astype("<f4")
    faces = points.reshape(-1, 3, 3)
    normals = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    normals = np.repeat(normals, 3, axis=0).astype("<f4")
    positions = points.tobytes()
    binary = positions + normals.tobytes()
    document = {
        "asset": {"version": "2.0", "generator": "NYC Building X-Ray single-building extraction"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "material": 0}]}],
        "materials": [{"doubleSided": True, "pbrMetallicRoughness": {"baseColorFactor": [0.68, 0.78, 0.74, 1], "metallicFactor": 0, "roughnessFactor": 0.8}}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(positions)}, {"buffer": 0, "byteOffset": len(positions), "byteLength": len(binary) - len(positions)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(points), "type": "VEC3", "min": points.min(axis=0).tolist(), "max": points.max(axis=0).tolist()}, {"bufferView": 1, "componentType": 5126, "count": len(points), "type": "VEC3"}],
    }
    data = json.dumps(document, separators=(",", ":")).encode()
    data += b" " * (-len(data) % 4)
    payload = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(data) + 8 + len(binary))
    payload += struct.pack("<II", len(data), 0x4E4F534A) + data
    payload += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(payload)
    return len(points) // 3


def extract_building(source: rhino3dm.File3dm, row: dict, output: Path) -> dict:
    polygon = Polygon(row["points"])
    scale = rhino3dm.UnitSystem.UnitScale(source.Settings.ModelUnitSystem, rhino3dm.UnitSystem.Millimeters)
    # One millimeter accommodates export roundoff at shared facade vertices.
    region = polygon.buffer(1 / scale)
    left, bottom, right, top = region.bounds
    selected = []
    triangles = []
    layer_counts: dict[str, int] = {}
    roles = layer_roles(source)
    for obj in source.Objects:
        layer = roles.get(obj.Attributes.LayerIndex)
        if layer not in {3, 4, 5, 6, 7, 8}:
            continue
        box = obj.Geometry.GetBoundingBox()
        if box.Min.X < left or box.Max.X > right or box.Min.Y < bottom or box.Max.Y > top:
            continue
        points = geometry_points(obj.Geometry)
        if not points or not region.covers(MultiPoint([(x, y) for x, y, _ in points]).convex_hull):
            # Concave footprint surfaces can have a convex hull outside the outline.
            if not points or not all(region.covers(Point(x, y)) for x, y, _ in points):
                continue
        selected.append(obj)
        layer_counts[str(layer)] = layer_counts.get(str(layer), 0) + 1
    surface_boundaries = set()
    for obj in selected:
        if isinstance(obj.Geometry, rhino3dm.Brep):
            for face in obj.Geometry.Faces:
                surface = face.DuplicateFace(False)
                triangles.extend(triangulate_surface(surface, scale))
                surface_boundaries.add(boundary_key(geometry_points(surface), scale))
    for obj in selected:
        if isinstance(obj.Geometry, rhino3dm.Curve):
            points = geometry_points(obj.Geometry)
            # An outer outline may omit a surface's inner hole boundaries.
            if not any(boundary_key(points, scale) <= boundary for boundary in surface_boundaries):
                triangles.extend(triangulate_outline([(x * scale, y * scale, z * scale) for x, y, z in points]))
    if not triangles or not all(str(layer) in layer_counts or str(layer + 3) in layer_counts for layer in (3, 4, 5)):
        raise ValueError("A complete footprint, roof, and facade could not be extracted")
    origin = [polygon.centroid.x * scale, polygon.centroid.y * scale, min(p[2] for p in triangles)]
    output.parent.mkdir(parents=True, exist_ok=True)
    triangle_count = write_glb(output.with_suffix(".glb"), triangles, origin)
    # Preserve the original source geometry as well as the browser rendering.
    model = rhino3dm.File3dm()
    model.Settings.ModelUnitSystem = source.Settings.ModelUnitSystem
    for material in source.Materials:
        model.Materials.Add(material)
    for layer in source.Layers:
        model.Layers.Add(layer)
    for obj in selected:
        model.Objects.Add(obj.Geometry, obj.Attributes)
    if not model.Write(str(output.with_suffix(".3dm")), 8):
        raise RuntimeError("Could not save isolated Rhino building")
    return {"object_count": len(selected), "triangle_count": triangle_count, "layer_counts": layer_counts, "origin_mm": origin}


def build_index(files: list[str] | None = None, force: bool = False) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    previous = json.loads(INDEX_PATH.read_text()) if INDEX_PATH.exists() else {}
    districts = {d["file"]: d for d in previous.get("districts", [])} if previous.get("version") == VERSION else {}
    paths = sorted(MODEL_DIR.glob("NYC_3DModel_*.3dm"))
    if files:
        unknown = set(files) - {p.name for p in paths}
        if unknown:
            raise ValueError(f"Model files not found: {', '.join(sorted(unknown))}")
        paths = [p for p in paths if p.name in files]
    for path in paths:
        existing = districts.get(path.name)
        sample = existing.get("sample") if existing else None
        if not force and existing and existing["stamp"] == source_stamp(path) and sample and all(
            (OUTPUT_DIR / f"{sample['name']}.{extension}").exists() for extension in ("glb", "3dm")
        ):
            print(f"Already prepared: {path.name}", flush=True)
            continue
        print(f"Indexing {path.name}…", flush=True)
        source = rhino3dm.File3dm.Read(str(path))
        if source is None:
            raise RuntimeError(f"Could not read {path}")
        rows = footprint_rows(source)
        if not rows:
            continue
        code = path.stem.removeprefix("NYC_3DModel_")
        stamp = source_stamp(path)
        revision = hashlib.sha256(f"{VERSION}:{stamp}".encode()).hexdigest()[:12]
        centers = np.asarray([Polygon(row["points"]).centroid.coords[0] for row in rows])
        center = np.median(centers, axis=0)
        # A source example is used only for explicitly fictional demo addresses.
        candidates = sorted(rows, key=lambda row: (Polygon(row["points"]).centroid.x - center[0]) ** 2 + (Polygon(row["points"]).centroid.y - center[1]) ** 2)
        sample = None
        for row in candidates[:30]:
            try:
                name = f"{code}-{revision}-{row['index']}"
                details = extract_building(source, row, OUTPUT_DIR / name)
                sample = {"name": name, "footprint_index": row["index"], **details}
                break
            except ValueError:
                continue
        scale = rhino3dm.UnitSystem.UnitScale(source.Settings.ModelUnitSystem, rhino3dm.UnitSystem.Millimeters)
        districts[path.name] = {"code": code, "borough": BOROUGHS[code[:2]], "file": path.name, "stamp": stamp, "revision": revision, "mm_per_unit": scale, "footprints": rows, "sample": sample}
        print(f"  {len(rows)} footprints; sample: {sample}", flush=True)
        del source
    temporary = INDEX_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"version": VERSION, "districts": list(districts.values())}, separators=(",", ":")))
    temporary.replace(INDEX_PATH)


def building_model(building: Building) -> dict:
    unavailable = {"status": "unavailable", "reason": "geometry_unavailable", "message": "No single-building model is available for this address in the uploaded districts."}
    if not INDEX_PATH.exists():
        return {**unavailable, "reason": "index_missing", "message": "Building models have not been prepared yet."}
    try:
        catalog = json.loads(INDEX_PATH.read_text())
    except (OSError, ValueError):
        return {**unavailable, "reason": "index_outdated", "message": "The building model index needs to be rebuilt."}
    if catalog.get("version") != VERSION:
        return {**unavailable, "reason": "index_outdated", "message": "The building model index needs to be updated."}
    districts = [d for d in catalog["districts"] if d["borough"] == building.borough and (MODEL_DIR / d["file"]).exists() and source_stamp(MODEL_DIR / d["file"]) == d["stamp"]]
    if building.demo:
        sample = next((d["sample"] for d in districts if d.get("sample")), None)
        if not sample:
            return unavailable
        return {"status": "ready", "match": "demo", "url": f"/models/buildings/{sample['name']}.glb", "download_url": f"/models/buildings/{sample['name']}.3dm", "message": "Single-building source example for this fictional demo address.", "object_count": sample["object_count"], "triangle_count": sample["triangle_count"]}
    if building.longitude is None or building.latitude is None or not all(math.isfinite(n) for n in (building.longitude, building.latitude)):
        return {**unavailable, "reason": "coordinates_missing", "message": "This address does not have a usable map location for matching its model."}
    x, y = TO_STATE_PLANE.transform(building.longitude, building.latitude)
    matches = [(district, row) for district in districts if (row := select_footprint(district["footprints"], x * MM_PER_FOOT / district["mm_per_unit"], y * MM_PER_FOOT / district["mm_per_unit"])) is not None]
    if len(matches) != 1:
        return unmatched_model(building, catalog)
    district, row = matches[0]
    name = f"{district['code']}-{district['revision']}-{row['index']}"
    output = OUTPUT_DIR / name
    metadata = output.with_suffix(".json")
    with EXTRACTION_LOCK:
        if not metadata.exists() or not output.with_suffix(".glb").exists() or not output.with_suffix(".3dm").exists():
            source = rhino3dm.File3dm.Read(str(MODEL_DIR / district["file"]))
            if source is None:
                return unavailable
            try:
                details = extract_building(source, row, output)
            except ValueError:
                return {**unavailable, "reason": "extraction_failed", "message": "This building's geometry could not be isolated reliably."}
            metadata.write_text(json.dumps(details))
        details = json.loads(metadata.read_text())
    return {"status": "ready", "match": "coordinate", "url": f"/models/buildings/{name}.glb", "download_url": f"/models/buildings/{name}.3dm", "message": "Matched to the footprint containing this address's map location. NYC source geometry, 2014 survey.", "object_count": details["object_count"], "triangle_count": details["triangle_count"]}
