"""
Generate the `videoList` content in script.js.

Usage:
  python process.py --id-file data/good_example
  python process.py --root demo_all --script script.js
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

VIDEO_LIST_START = "// === VIDEO LIST START (auto-generated) ==="
VIDEO_LIST_END = "// === VIDEO LIST END ==="


def read_ids_from_file(path: Path) -> List[str]:
    """Read video IDs (first column per line) from a file."""
    ids: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ids.append(line.split(",")[0].strip())
    return ids


def discover_ids(root: Path) -> List[str]:
    """Scan demo_root for .mp4 files and return their base names."""
    ids = {p.name for p in root.rglob("*.mp4")}
    return sorted(ids)


def resolve_models(root: Path, models: Iterable[str] | None) -> List[str]:
    if models:
        return list(models)
    return sorted([p.name for p in root.iterdir() if p.is_dir()])


def build_entries(
    video_ids: Iterable[str], models: Iterable[str], demo_root: Path, public_prefix: str
) -> List[str]:
    entries: List[str] = []
    physics_root = Path("physics_gpt_outputs_with_force")
    for video in video_ids:
        for model in models:
            full_path = demo_root / model / video
            if not full_path.exists():
                continue
            prompt_img, prompt_txt, prompt_txt_content = find_prompt_assets(video, physics_root)
            fields = [
                f'src: "{public_prefix}/{model}/{video}"',
                f'id: "{model}/{video}"',
            ]
            if prompt_img:
                fields.append(f'promptImg: "{prompt_img}"')
            if prompt_txt:
                fields.append(f'promptText: "{prompt_txt}"')
            if prompt_txt_content:
                clean = (
                    prompt_txt_content.replace("\\", "\\\\")
                    .replace('"', '\\"')
                    .replace("\r", "")
                    .replace("\n", "\\n")
                )
                fields.append(f'promptTextContent: "{clean}"')
            entries.append("  { " + ", ".join(fields) + " },")
    return entries


def find_prompt_assets(
    video_name: str, physics_root: Path
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Locate prompt image/text for a given video by matching filename in physics_gpt_outputs_with_force.
    Returns (image_path, text_path, text_content) relative to project root if found.
    """
    stem = Path(video_name).stem
    if not physics_root.exists():
        return None, None, None

    for sub in physics_root.iterdir():
        if not sub.is_dir():
            continue
        img = sub / f"{stem}_frame0.jpg"
        txt = sub / f"{stem}.txt"
        img_path = img.as_posix() if img.exists() else None
        txt_path = txt.as_posix() if txt.exists() else None
        txt_content = None
        if txt_path:
            try:
                txt_content = txt.read_text(encoding="utf-8")
            except Exception:
                txt_content = None
        if img_path or txt_path:
            return img_path, txt_path, txt_content
    return None, None, None


def update_script_js(script_path: Path, entries: List[str]) -> None:
    content = script_path.read_text(encoding="utf-8")
    start_idx = content.find(VIDEO_LIST_START)
    end_idx = content.find(VIDEO_LIST_END)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise RuntimeError("videoList markers not found in script.js")

    before = content[: start_idx + len(VIDEO_LIST_START)]
    start_line_start = content.rfind("\n", 0, start_idx)
    start_indent = content[start_line_start + 1 : start_idx] if start_line_start != -1 else ""

    end_line_start = content.rfind("\n", 0, end_idx)
    end_indent = content[end_line_start + 1 : end_idx] if end_line_start != -1 else ""
    indent = end_indent or start_indent
    after = indent + content[end_idx:]

    body = "\n" + "\n".join(entries if entries else ["  // (no videos found)"]) + "\n"
    script_path.write_text(before + body + after, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate videoList in script.js")
    parser.add_argument(
        "--id-file",
        type=Path,
        help="Optional file containing video IDs (uses first column, comma-separated).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("demo_all"),
        help="Root directory containing model subfolders and .mp4 files.",
    )
    parser.add_argument(
        "--script", type=Path, default=Path("script.js"), help="Path to script.js"
    )
    parser.add_argument(
        "--models",
        nargs="*",
        help="Model folder names to include. Defaults to all subfolders in --root.",
    )
    parser.add_argument(
        "--public-prefix",
        default=None,
        help="Prefix to use in src paths (defaults to the --root value).",
    )

    args = parser.parse_args()

    if not args.root.exists():
        raise FileNotFoundError(f"Video root not found: {args.root}")

    demo_root = args.root
    public_prefix = args.public_prefix or demo_root.as_posix()

    if args.id_file:
        if not args.id_file.exists():
            raise FileNotFoundError(f"ID file not found: {args.id_file}")
        video_ids = read_ids_from_file(args.id_file)
    else:
        video_ids = discover_ids(demo_root)

    models = resolve_models(demo_root, args.models)
    entries = build_entries(video_ids, models, demo_root, public_prefix)

    update_script_js(args.script, entries)
    print(f"Updated {args.script} with {len(entries)} entries.")


if __name__ == "__main__":
    main()
