import json
import struct
from types import SimpleNamespace

import numpy as np
import pytest
import rhino3dm
from shapely import Polygon

from app.fixtures import BUILDINGS
from app.services import building_models as models


def row(points, index=0):
    return {"index": index, "points": points, "bounds": list(Polygon(points).bounds)}


def test_matching_requires_one_containing_footprint():
    left = row([(0, 0), (10, 0), (10, 10), (0, 10)])
    right = row([(10, 0), (20, 0), (20, 10), (10, 10)], 1)
    assert models.select_footprint([left, right], 5, 5) == left
    assert models.select_footprint([left, right], 15, 5) == right
    assert models.select_footprint([left, right], 10, 5) is None
    assert models.select_footprint([left, right], 100, 5) is None
    assert models.select_footprint([left, left], 5, 5) is None


def test_concave_roof_keeps_its_notch_and_all_boundary_corners():
    outline = [(0, 0, 8), (4, 0, 8), (4, 2, 8), (2, 2, 8), (2, 4, 8), (0, 4, 8), (0, 0, 8)]
    triangles = models.triangulate_outline(outline)
    roof = Polygon([(p[0], p[1]) for p in outline])
    polygons = [Polygon([(p[0], p[1]) for p in triangles[i:i + 3]]) for i in range(0, len(triangles), 3)]
    assert sum(p.area for p in polygons) == pytest.approx(roof.area)
    assert all(roof.covers(p) for p in polygons)
    assert set(outline[:-1]) <= {tuple(p) for p in triangles}


def test_surface_triangulation_preserves_roof_openings():
    edges = [rhino3dm.PolylineCurve([rhino3dm.Point3d(x, y, 10) for x, y in loop])
             for loop in ([(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)],
                          [(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])]
    triangles = models.triangulate_surface(SimpleNamespace(Edges=edges), 1)
    polygons = [Polygon([(p[0], p[1]) for p in triangles[i:i + 3]]) for i in range(0, len(triangles), 3)]
    opening = Polygon([(1, 1), (3, 1), (3, 3), (1, 3)])
    assert sum(p.area for p in polygons) == pytest.approx(12)
    assert all(p.intersection(opening).area < 1e-9 for p in polygons)


@pytest.mark.parametrize("units", [rhino3dm.UnitSystem.Feet, rhino3dm.UnitSystem.Millimeters])
def test_extraction_preserves_roof_and_excludes_neighbor(tmp_path, units):
    source = rhino3dm.File3dm()
    source.Settings.ModelUnitSystem = units
    scale = rhino3dm.UnitSystem.UnitScale(rhino3dm.UnitSystem.Meters, units)
    # Deliberately use a different layer order to catch hard-coded layer indexes.
    layers = {}
    for name in ("Building_Facade", "Building_RoofTop", "Building_FootPrint", "Surface_RoofTop"):
        layer = rhino3dm.Layer()
        layer.Name = name
        layers[name] = source.Layers.Add(layer)

    def add_polygon(name, points):
        attributes = rhino3dm.ObjectAttributes()
        attributes.LayerIndex = layers[name]
        curve = rhino3dm.PolylineCurve([rhino3dm.Point3d(x * scale, y * scale, z * scale) for x, y, z in points])
        source.Objects.AddCurve(curve, attributes)

    for offset in (0, 20):
        for z, name in ((0, "Building_FootPrint"), (10, "Building_RoofTop")):
            add_polygon(name, [(offset, 0, z), (offset + 10, 0, z), (offset + 10, 10, z), (offset, 10, z), (offset, 0, z)])
        base = [(offset, 0), (offset + 10, 0), (offset + 10, 10), (offset, 10), (offset, 0)]
        for a, b in zip(base, base[1:]):
            add_polygon("Building_Facade", [(*a, 0), (*b, 0), (*b, 10), (*a, 10), (*a, 0)])
    # A small rooftop feature must survive extraction without simplification.
    add_polygon("Building_RoofTop", [(3, 3, 11), (4, 3, 11), (4, 4, 11), (3, 4, 11), (3, 3, 11)])
    # Some source details are surfaces without a duplicate linework object.
    outline = rhino3dm.PolylineCurve([rhino3dm.Point3d(x * scale, y * scale, 12 * scale)
                                     for x, y in [(5, 5), (6, 5), (6, 6), (5, 6), (5, 5)]])
    plane = rhino3dm.Plane(rhino3dm.Point3d(0, 0, 12 * scale), rhino3dm.Vector3d(0, 0, 1))
    surface_attributes = rhino3dm.ObjectAttributes()
    surface_attributes.LayerIndex = layers["Surface_RoofTop"]
    source.Objects.AddBrep(rhino3dm.Brep.CreateTrimmedPlane(plane, outline), surface_attributes)
    footprints = models.footprint_rows(source)
    assert len(footprints) == 2
    selected = models.select_footprint(footprints, scale * 5, scale * 5)
    details = models.extract_building(source, selected, tmp_path / "building")
    assert details["object_count"] == 8
    exported = rhino3dm.File3dm.Read(str(tmp_path / "building.3dm"))
    assert len(exported.Objects) == 8
    assert exported.Settings.ModelUnitSystem == units
    assert all(o.Geometry.GetBoundingBox().Max.X <= 10 * scale + 1e-6 for o in exported.Objects)
    data = (tmp_path / "building.glb").read_bytes()
    magic, version, length = struct.unpack_from("<III", data)
    assert (magic, version, length) == (0x46546C67, 2, len(data))
    json_length = struct.unpack_from("<I", data, 12)[0]
    document = json.loads(data[20:20 + json_length])
    position = document["accessors"][0]
    assert np.subtract(position["max"], position["min"]) == pytest.approx([10, 12, 10])


def test_missing_catalog_does_not_substitute_a_district(monkeypatch, tmp_path):
    monkeypatch.setattr(models, "INDEX_PATH", tmp_path / "missing.json")
    live = BUILDINGS[0].model_copy(update={"demo": False})
    assert models.building_model(live)["status"] == "unavailable"


@pytest.mark.parametrize("source_exists,reason", [(False, "missing_district"), (True, "index_outdated")])
def test_missing_mn06_is_distinguished_from_extraction_failure(monkeypatch, tmp_path, source_exists, reason):
    monkeypatch.setattr(models, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(models, "community_district", lambda building: "MN06")
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"version": models.VERSION, "districts": []}))
    monkeypatch.setattr(models, "INDEX_PATH", index)
    if source_exists:
        (tmp_path / "NYC_3DModel_MN06.3dm").touch()
    building = BUILDINGS[0].model_copy(update={"demo": False, "borough": "Manhattan",
        "address": "317 EAST 18 STREET", "latitude": 40.734615, "longitude": -73.982127})
    result = models.building_model(building)
    assert result["reason"] == reason
    assert result["required_district"] == "MN06"
    assert result["required_file"] == "NYC_3DModel_MN06.3dm"
    assert "Manhattan Community District 6" in result["message"]
    assert "url" not in result


def test_district_lookup_validates_and_caches_pluto_response(monkeypatch):
    monkeypatch.setattr(models, "get_cache", lambda *args, **kwargs: None)
    stored = {}
    monkeypatch.setattr(models, "set_cache", lambda key, value: stored.update({key: value}))
    def fetch(url, params, timeout):
        assert params["bbl"] == "1009240013"
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: [{"bbl": "1009240013.00000000", "cd": "106"}])
    monkeypatch.setattr(models.httpx, "get", fetch)
    building = BUILDINGS[0].model_copy(update={"bbl": "1009240013"})
    assert models.community_district(building) == "MN06"
    assert stored["model-district:1009240013"] == {"district": "MN06"}
    monkeypatch.setattr(models.httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(models.httpx.ConnectError("offline")))
    assert models.community_district(building) is None


def test_preparing_one_unchanged_district_preserves_other_districts(monkeypatch, tmp_path):
    monkeypatch.setattr(models, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(models, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(models, "INDEX_PATH", tmp_path / "index.json")
    districts = []
    for code in ("MN06", "MN08"):
        source = tmp_path / f"NYC_3DModel_{code}.3dm"
        source.touch()
        for suffix in ("glb", "3dm"):
            (tmp_path / f"{code}-sample.{suffix}").touch()
        districts.append({"file": source.name, "stamp": models.source_stamp(source), "sample": {"name": f"{code}-sample"}})
    models.INDEX_PATH.write_text(json.dumps({"version": models.VERSION, "districts": districts}))
    # Empty source files cannot be parsed: success proves neither was reopened.
    models.build_index(["NYC_3DModel_MN06.3dm"])
    assert json.loads(models.INDEX_PATH.read_text())["districts"] == districts
