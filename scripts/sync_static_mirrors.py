"""
sync_static_mirrors.py — keeps the legacy root static/ folder identical to the
copies under antigravity_core/static/ (the ones the FastAPI app actually
serves), so the two can never silently drift apart again.

Run automatically by the .githooks/pre-commit hook before every commit.
Safe to run manually too: `python scripts/sync_static_mirrors.py`
"""
import filecmp
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "antigravity_core" / "static"
MIRROR_DIR = REPO_ROOT / "static"

# Extra one-off mirrors that live outside the static/ folders.
EXTRA_MIRRORS = [
    (SOURCE_DIR / "rythm.html", REPO_ROOT / "rythm.html"),
]


def _copy_if_changed(source: Path, dest: Path) -> bool:
    if not source.is_file():
        return False
    if dest.exists() and filecmp.cmp(source, dest, shallow=False):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return True


def sync() -> list[str]:
    """Copy every file that exists in both SOURCE_DIR and MIRROR_DIR when it differs. Returns updated relative paths."""
    updated = []
    for source_file in sorted(SOURCE_DIR.iterdir()):
        if not source_file.is_file():
            continue
        mirror_file = MIRROR_DIR / source_file.name
        if not mirror_file.exists():
            continue  # only sync files the mirror already knows about — new files are added deliberately
        if _copy_if_changed(source_file, mirror_file):
            updated.append(str(mirror_file.relative_to(REPO_ROOT)))

    for source_file, dest_file in EXTRA_MIRRORS:
        if _copy_if_changed(source_file, dest_file):
            updated.append(str(dest_file.relative_to(REPO_ROOT)))

    return updated


if __name__ == "__main__":
    changed = sync()
    if changed:
        print(f"[sync_static_mirrors] Updated {len(changed)} file(s): {', '.join(changed)}")
    else:
        print("[sync_static_mirrors] Mirrors already in sync.")
