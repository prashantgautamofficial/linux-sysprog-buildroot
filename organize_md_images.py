#!/usr/bin/env python3
"""
organize_md_images.py

Moves image files referenced in Markdown into a subfolder and rewrites
the Markdown image references to point to the new location.

Two modes:

1) Single-file mode (original behavior):
   Moves images into an "images/" folder next to that one .md file.

       python organize_md_images.py path/to/file.md
       python organize_md_images.py path/to/file.md --images-dir images
       python organize_md_images.py path/to/file.md --dry-run

2) Recursive mode:
   Walks a directory tree, processes every .md file found, and pools
   ALL images from ALL of them into a single shared folder created at
   the root of that directory. Filename collisions between different
   source files are handled automatically (see below).

       python organize_md_images.py path/to/project --recursive
       python organize_md_images.py path/to/project -r --images-dir assets
       python organize_md_images.py path/to/project -r --dry-run

By default the .md file(s) are edited in place (a .bak backup is
written first for each). Use --dry-run to preview without touching
anything. Use --no-backup to skip the backup copies.

Collision handling (recursive mode only):
   If two different source images would land on the same filename in
   the shared folder (e.g. "image-1.png" used in two different
   subfolders' .md files), the second one is renamed with a short
   suffix derived from its original relative path, e.g.
   "image-1__sub2.png", so nothing is silently overwritten.
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

# Matches Markdown image syntax: ![alt text](path "optional title")
IMAGE_PATTERN = re.compile(
    r'(!\[[^\]]*\]\()'      # group 1: "![alt](" 
    r'([^)\s]+)'            # group 2: the path (no spaces/close-paren)
    r'((?:\s+"[^"]*")?\))'  # group 3: optional title + closing paren
)


def is_local_image(path: str) -> bool:
    """Skip URLs (http/https) and anything already inside a folder we manage."""
    if path.startswith(("http://", "https://", "//")):
        return False
    return True


def already_in_images_dir(ref_path_norm: str, images_dir_name: str) -> bool:
    return ref_path_norm == images_dir_name or ref_path_norm.startswith(f"{images_dir_name}/")


def unique_dest_name(dest_dir: Path, desired_name: str, src_path: Path,
                      claimed: dict) -> str:
    """
    Return a filename to use inside dest_dir for src_path, avoiding
    collisions with:
      - files already physically present in dest_dir
      - names already claimed by a *different* source file in this run
    `claimed` maps final_name -> source Path, shared across the whole run.
    """
    if desired_name not in claimed and not (dest_dir / desired_name).exists():
        claimed[desired_name] = src_path
        return desired_name

    # If the exact same source file already claimed this name, reuse it.
    if claimed.get(desired_name) == src_path:
        return desired_name

    # Collision: build a suffix from the source file's parent folder name.
    stem = Path(desired_name).stem
    suffix = Path(desired_name).suffix
    tag = src_path.parent.name or "f"
    candidate = f"{stem}__{tag}{suffix}"
    n = 2
    while candidate in claimed or (dest_dir / candidate).exists():
        candidate = f"{stem}__{tag}{n}{suffix}"
        n += 1
    claimed[candidate] = src_path
    return candidate


def process_one_md(md_path: Path, images_dir: Path, images_dir_ref_prefix: str,
                    claimed: dict, dry_run: bool, make_backup: bool):
    """
    Process a single markdown file:
      - find local image references
      - plan moves into images_dir (using images_dir_ref_prefix as the
        relative path written into the markdown, e.g. "images" or
        "../images" depending on nesting)
      - move files and rewrite references (unless dry_run)

    Returns a summary dict for reporting.
    """
    base_dir = md_path.parent
    text = md_path.read_text(encoding="utf-8")
    matches = list(IMAGE_PATTERN.finditer(text))

    summary = {
        "md_path": md_path,
        "total_refs": len(matches),
        "moved": 0,
        "skipped_urls": 0,
        "missing": [],
        "planned_moves": [],  # (src, dst) for dry-run reporting
    }

    if not matches:
        return summary

    # ref_path (as written in this file) -> final new relative path to write
    rewrite_map = {}

    for m in matches:
        ref_path = m.group(2)

        if not is_local_image(ref_path):
            summary["skipped_urls"] += 1
            continue

        ref_path_norm = ref_path.replace("\\", "/")
        if already_in_images_dir(ref_path_norm, images_dir_ref_prefix.rstrip("/")):
            continue

        if ref_path in rewrite_map:
            continue  # already resolved this exact reference

        src = (base_dir / ref_path).resolve()
        if not src.is_file():
            summary["missing"].append(ref_path)
            continue

        desired_name = Path(ref_path).name
        final_name = unique_dest_name(images_dir, desired_name, src, claimed)
        new_rel = f"{images_dir_ref_prefix}/{final_name}"
        rewrite_map[ref_path] = new_rel
        summary["planned_moves"].append((src, images_dir / final_name))

    if dry_run:
        return summary

    # --- Execute moves ---
    for src, dst in summary["planned_moves"]:
        if dst.exists() and dst.resolve() == src.resolve():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        summary["moved"] += 1

    # --- Backup + rewrite markdown ---
    if rewrite_map:
        if make_backup:
            backup_path = md_path.with_suffix(md_path.suffix + ".bak")
            shutil.copy2(md_path, backup_path)
            summary["backup_path"] = backup_path

        def replace(m: re.Match) -> str:
            ref_path = m.group(2)
            if ref_path in rewrite_map:
                return f"{m.group(1)}{rewrite_map[ref_path]}{m.group(3)}"
            return m.group(0)

        new_text = IMAGE_PATTERN.sub(replace, text)
        md_path.write_text(new_text, encoding="utf-8")

    return summary


def run_single(md_file: Path, images_dir_name: str, dry_run: bool, make_backup: bool):
    md_path = md_file.resolve()
    if not md_path.is_file():
        sys.exit(f"Error: markdown file not found: {md_path}")

    base_dir = md_path.parent
    images_dir = base_dir / images_dir_name
    claimed = {}

    print(f"Markdown file : {md_path}")
    print(f"Images folder : {images_dir}")

    if not dry_run:
        images_dir.mkdir(parents=True, exist_ok=True)

    summary = process_one_md(
        md_path, images_dir, images_dir_name, claimed, dry_run, make_backup
    )

    print(f"Found {summary['total_refs']} image reference(s); "
          f"{len(summary['planned_moves'])} unique local file(s) to move; "
          f"{summary['skipped_urls']} remote URL(s) skipped.")

    if summary["missing"]:
        print("\nWARNING: these referenced files were not found on disk "
              "(references will still be rewritten if run for real):")
        for p in summary["missing"]:
            print(f"  - {p}")

    if dry_run:
        print("\n[Dry run] Planned moves:")
        for src, dst in summary["planned_moves"]:
            print(f"  {src}  ->  {dst}")
        print("\n[Dry run] No files moved, no markdown changed.")
        return

    for src, dst in summary["planned_moves"]:
        print(f"  Moved: {src.name} -> {dst.relative_to(base_dir)}")
    if summary.get("backup_path"):
        print(f"  Backup written: {summary['backup_path']}")

    print(f"\nDone. {summary['moved']} file(s) moved into "
          f"'{images_dir_name}/', markdown references updated.")


def run_recursive(root: Path, images_dir_name: str, dry_run: bool, make_backup: bool):
    root = root.resolve()
    if not root.is_dir():
        sys.exit(f"Error: not a directory: {root}")

    images_dir = root / images_dir_name
    md_files = sorted(p for p in root.rglob("*.md") if p.resolve() != images_dir)
    # Exclude any .md files that happen to live inside the images dir itself
    md_files = [p for p in md_files if images_dir not in p.parents]

    if not md_files:
        print(f"No .md files found under {root}. Nothing to do.")
        return

    print(f"Root directory : {root}")
    print(f"Shared images  : {images_dir}")
    print(f"Found {len(md_files)} markdown file(s):")
    for p in md_files:
        print(f"  - {p.relative_to(root)}")
    print()

    if not dry_run:
        images_dir.mkdir(parents=True, exist_ok=True)

    claimed = {}  # shared across ALL files so collisions are caught globally
    total_moved = 0
    total_refs = 0
    total_skipped_urls = 0
    all_missing = []

    for md_path in md_files:
        # Relative path from this .md file's folder back to the shared
        # images dir, so references still work regardless of nesting depth.
        rel = Path(os.path.relpath(images_dir, start=md_path.parent)).as_posix()

        summary = process_one_md(
            md_path, images_dir, rel, claimed, dry_run, make_backup
        )
        total_refs += summary["total_refs"]
        total_skipped_urls += summary["skipped_urls"]
        all_missing.extend(
            f"{md_path.relative_to(root)}: {m}" for m in summary["missing"]
        )

        if summary["planned_moves"] or summary["total_refs"]:
            print(f"[{md_path.relative_to(root)}] "
                  f"{summary['total_refs']} ref(s), "
                  f"{len(summary['planned_moves'])} to move")
            if dry_run:
                for src, dst in summary["planned_moves"]:
                    print(f"    {src}  ->  {dst}")
            else:
                for src, dst in summary["planned_moves"]:
                    print(f"    Moved: {src.name} -> {dst.relative_to(root)}")
                if summary.get("backup_path"):
                    print(f"    Backup: {summary['backup_path'].relative_to(root)}")
                total_moved += summary["moved"]

    print(f"\nTotals: {total_refs} reference(s) found across {len(md_files)} file(s); "
          f"{total_skipped_urls} remote URL(s) skipped.")

    if all_missing:
        print("\nWARNING: referenced files not found on disk:")
        for m in all_missing:
            print(f"  - {m}")

    if dry_run:
        print("\n[Dry run] No files moved, no markdown changed.")
    else:
        print(f"\nDone. {total_moved} file(s) moved into "
              f"'{images_dir_name}/' at the project root, "
              f"markdown references updated across {len(md_files)} file(s).")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a Markdown file, or (with --recursive) a directory to scan",
    )
    parser.add_argument(
        "--images-dir",
        default="images",
        help="Name of the folder to move images into (default: images)",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Treat 'path' as a directory; process every .md file under it "
             "and pool all images into one shared folder at its root",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without moving files or editing markdown",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't write .bak copies of the original markdown files",
    )
    args = parser.parse_args()

    make_backup = not args.no_backup

    if args.recursive:
        run_recursive(args.path, args.images_dir, args.dry_run, make_backup)
    else:
        run_single(args.path, args.images_dir, args.dry_run, make_backup)


if __name__ == "__main__":
    main()
