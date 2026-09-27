from __future__ import annotations

import argparse
import heapq
import statistics
from pathlib import Path

import rhino3dm


ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "public" / "models"
OUTPUT_DIR = MODELS_DIR / "previews"
BUILDING_LAYERS = {3, 4, 5, 6, 7, 8}
HALF_WINDOW_MM = 60_000
MAX_OBJECTS = 8_000


def intersects_window(box: rhino3dm.BoundingBox, center_x: float, center_y: float) -> bool:
    return (
        box.Max.X >= center_x - HALF_WINDOW_MM
        and box.Min.X <= center_x + HALF_WINDOW_MM
        and box.Max.Y >= center_y - HALF_WINDOW_MM
        and box.Min.Y <= center_y + HALF_WINDOW_MM
    )


def build_preview(source_path: Path) -> None:
    source = rhino3dm.File3dm.Read(str(source_path))
    if source is None:
        raise RuntimeError(f"Could not read {source_path.name}")

    candidate_centers: list[tuple[float, float]] = []
    for model_object in source.Objects:
        if model_object.Attributes.LayerIndex not in BUILDING_LAYERS:
            continue
        box = model_object.Geometry.GetBoundingBox()
        width = box.Max.X - box.Min.X
        depth = box.Max.Y - box.Min.Y
        if width <= 0 or depth <= 0 or width > 250_000 or depth > 250_000:
            continue
        candidate_centers.append(((box.Min.X + box.Max.X) / 2, (box.Min.Y + box.Max.Y) / 2))

    if not candidate_centers:
        raise RuntimeError(f"No building geometry found in {source_path.name}")

    center_x = statistics.median(point[0] for point in candidate_centers)
    center_y = statistics.median(point[1] for point in candidate_centers)
    preview = rhino3dm.File3dm()
    for material in source.Materials:
        preview.Materials.Add(material)
    for layer in source.Layers:
        preview.Layers.Add(layer)

    candidates: list[tuple[float, int]] = []
    for index, model_object in enumerate(source.Objects):
        if model_object.Attributes.LayerIndex not in BUILDING_LAYERS:
            continue
        box = model_object.Geometry.GetBoundingBox()
        if box.Max.X - box.Min.X > 250_000 or box.Max.Y - box.Min.Y > 250_000:
            continue
        if not intersects_window(box, center_x, center_y):
            continue
        object_x = (box.Min.X + box.Max.X) / 2
        object_y = (box.Min.Y + box.Max.Y) / 2
        distance = (object_x - center_x) ** 2 + (object_y - center_y) ** 2
        candidates.append((distance, index))

    selected_indices = {index for _, index in heapq.nsmallest(MAX_OBJECTS, candidates)}
    for index in sorted(selected_indices):
        model_object = source.Objects[index]
        preview.Objects.Add(model_object.Geometry, model_object.Attributes)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{source_path.stem}-preview.3dm"
    if not preview.Write(str(output_path), 8):
        raise RuntimeError(f"Could not write {output_path.name}")
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"{source_path.name}: {len(selected_indices)} objects -> {size_mb:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create browser-sized previews from NYC district Rhino models.")
    parser.add_argument("files", nargs="*", help="Optional model filenames; defaults to every top-level .3dm file")
    args = parser.parse_args()
    source_paths = [MODELS_DIR / name for name in args.files] if args.files else sorted(MODELS_DIR.glob("*.3dm"))
    for source_path in source_paths:
        build_preview(source_path)


if __name__ == "__main__":
    main()
