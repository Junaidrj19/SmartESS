#!/usr/bin/env python3
"""Bundle the frozen scientific artifacts required to deploy the canonical case.

Copies nothing into Git. Does not regenerate models, scores, evaluation, the
healthy reference, the corpus, or investigations. The tarball is a byte-for-byte
archive of the working host's existing files.
"""

from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "deploy"
ARCHIVE = OUT_DIR / "smartess-scientific-artifacts.tar"
MANIFEST = OUT_DIR / "scientific-artifacts.manifest"

MODEL_ID = "iforest-v1-syn-sic-pc-dev-001-s20260922"


def _files() -> list[Path]:
    paths: list[Path] = []
    paths.extend(sorted((REPO / "ml/datasets/features/v1").glob("*.parquet")))
    model = REPO / f"ml/models/{MODEL_ID}"
    paths.extend(sorted(p for p in model.rglob("*") if p.is_file() and p.name != ".DS_Store"))
    scores = REPO / f"ml/datasets/scores/{MODEL_ID}"
    paths.extend(sorted(p for p in scores.rglob("*") if p.is_file() and p.name != ".DS_Store"))
    evaluation = REPO / f"ml/datasets/evaluation/{MODEL_ID}"
    paths.extend(sorted(p for p in evaluation.rglob("*") if p.is_file() and p.name != ".DS_Store"))
    paths.append(REPO / "ml/datasets/investigations/reference/healthy-reference.json")
    chroma = REPO / "knowledge_base/chroma"
    paths.extend(sorted(p for p in chroma.rglob("*") if p.is_file() and p.name != ".DS_Store"))
    paths.extend(sorted((REPO / "knowledge_base/corpus").rglob("*.pdf")))
    investigations = REPO / "ml/datasets/investigations"
    for d in sorted(investigations.glob("inv-*")):
        if d.is_dir():
            paths.extend(sorted(p for p in d.rglob("*") if p.is_file() and p.name != ".DS_Store"))
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise SystemExit("missing required artifact: " + str(missing[0].relative_to(REPO)))
    return paths


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    files = _files()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    with tarfile.open(ARCHIVE, "w") as tar:
        for path in files:
            rel = path.relative_to(REPO).as_posix()
            digest = _sha256(path)
            lines.append(f"{digest}  {path.stat().st_size}  {rel}")
            tar.add(path, arcname=rel, recursive=False)
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"files: {len(files)}")
    print(f"archive: {ARCHIVE.relative_to(REPO)} ({ARCHIVE.stat().st_size} bytes)")
    print(f"manifest: {MANIFEST.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
