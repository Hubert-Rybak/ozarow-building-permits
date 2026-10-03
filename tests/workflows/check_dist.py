#!/usr/bin/env python3
"""Fail closed before Pages upload: public snapshot only, no private input files."""
from pathlib import Path
import sys

DATA_FILES = frozenset({"permits.json", "parcels.geojson", "metadata.json"})
ASSET_SUFFIXES = frozenset({".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf"})
ROOT = Path(__file__).resolve().parents[2]


def validate(dist: Path, public_data: Path) -> None:
    if not dist.is_dir() or dist.is_symlink():
        raise ValueError("Missing real dist directory")
    if {path.name for path in dist.iterdir()} != {"index.html", "assets", "data"}:
        raise ValueError("Unexpected distribution root; only index.html, assets/, data/ allowed")
    data = dist / "data"
    if not data.is_dir() or {path.name for path in data.iterdir()} != DATA_FILES:
        raise ValueError("Distribution must contain exactly the three public data files")
    if not (dist / "index.html").is_file():
        raise ValueError("Missing built index.html")
    if not any((dist / "assets").glob("*.js")):
        raise ValueError("Missing built application JavaScript")
    for path in dist.rglob("*"):
        relative = path.relative_to(dist)
        if path.is_symlink() or any(part.startswith(".") for part in relative.parts):
            raise ValueError(f"Hidden path or symlink not allowed: {relative}")
        if path.is_dir():
            if relative.parts[0] not in {"assets", "data"}:
                raise ValueError(f"Unexpected directory: {relative}")
            continue
        if not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError(f"Non-regular file or hard link: {relative}")
        if relative.parts[0] == "assets" and path.suffix.lower() not in ASSET_SUFFIXES:
            raise ValueError(f"Unexpected asset type: {relative}")
        if relative.parts[0] == "data" and len(relative.parts) != 2:
            raise ValueError(f"Unexpected data subtree: {relative}")
    for name in DATA_FILES:
        source = public_data / name
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Invalid public source snapshot: {name}")
        if (data / name).read_bytes() != source.read_bytes():
            raise ValueError(f"Build copied a different data generation: {name}")


if __name__ == "__main__":
    try:
        validate(ROOT / "dist", ROOT / "public/data")
    except (OSError, ValueError) as exc:
        sys.exit(f"Pages artifact rejected: {exc}")
    print("Pages artifact verified: dist/; exact three-file public snapshot; no raw/cache/link files")
