"""Index original district models and prepare isolated single-building examples."""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.building_models import build_index

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="Optional original model filenames to prepare")
    parser.add_argument("--force", action="store_true", help="Rebuild unchanged districts too")
    args = parser.parse_args()
    build_index(args.files, force=args.force)
