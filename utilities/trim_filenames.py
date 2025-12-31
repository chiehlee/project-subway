
# poetry run python utilities/trim_filenames.py

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _unique_path(p: Path) -> Path:
	if not p.exists():
		return p
	stem, suffix = p.stem, p.suffix
	for i in range(1, 10_000):
		candidate = p.with_name(f"{stem}_{i}{suffix}")
		if not candidate.exists():
			return candidate
	raise RuntimeError(f"Unable to find unique name for: {p}")


def replace_spaces_with_underscores(root: Path, *, dry_run: bool = False) -> tuple[int, int]:
	"""Rename all files/folders under `root` replacing spaces with underscores.

	Depth-first (children first) so parent renames don't break traversal.
	Returns (renamed_count, skipped_count).
	"""

	root = root.expanduser().resolve()
	if not root.exists():
		raise FileNotFoundError(str(root))

	items = sorted((p for p in root.rglob("*") if p.name), key=lambda p: len(p.parts), reverse=True)
	renamed = 0
	skipped = 0

	for src in items:
		if " " not in src.name:
			skipped += 1
			continue
		dst = src.with_name(src.name.replace(" ", "_"))
		if dst == src:
			skipped += 1
			continue
		dst = _unique_path(dst)
		if not dry_run:
			src.rename(dst)
		renamed += 1

	return renamed, skipped


if __name__ == "__main__":
	renamed, skipped = replace_spaces_with_underscores(PROJECT_ROOT)
	print(f"Renamed: {renamed} | Skipped: {skipped} | Root: {PROJECT_ROOT}")

