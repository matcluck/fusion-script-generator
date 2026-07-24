#!/usr/bin/env python3
"""Look up Autodesk Fusion Python API signatures in the local installed stubs."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


CLASS_RE = re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\(")
METHOD_RE = re.compile(r"^\s+def\s+([A-Za-z_][A-Za-z0-9_]*)\(")


def newest_adsk_package() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None

    production = Path(local_app_data) / "Autodesk" / "webdeploy" / "production"
    candidates = []
    for path in production.glob("*/Api/Python/packages/adsk"):
        if path.is_dir():
            marker = path / "fusion.py"
            try:
                mtime = marker.stat().st_mtime if marker.exists() else path.stat().st_mtime
            except OSError:
                continue
            candidates.append((mtime, path))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def stub_files(adsk_package: Path) -> list[Path]:
    preferred = ["core.py", "fusion.py", "cam.py"]
    files = [adsk_package / name for name in preferred if (adsk_package / name).exists()]
    other_files = sorted(path for path in adsk_package.glob("*.py") if path not in files)
    return files + other_files


def line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def find_class(lines: list[str], class_name: str) -> tuple[int, int] | None:
    start = None
    for index, line in enumerate(lines):
        match = CLASS_RE.match(line)
        if not match:
            continue
        if match.group(1) == class_name:
            start = index
            continue
        if start is not None:
            return start, index
    if start is not None:
        return start, len(lines)
    return None


def find_method(lines: list[str], start: int, end: int, method_name: str) -> tuple[int, int] | None:
    method_start = None
    method_indent = None
    for index in range(start + 1, end):
        match = METHOD_RE.match(lines[index])
        if not match:
            continue
        if method_start is None and match.group(1) == method_name:
            method_start = index
            method_indent = line_indent(lines[index])
            continue
        if method_start is not None and line_indent(lines[index]) <= method_indent:
            return method_start, index
    if method_start is not None:
        return method_start, end
    return None


def find_member(
    lines: list[str], start: int, end: int, member_name: str
) -> tuple[tuple[int, int], str] | None:
    method_span = find_method(lines, start, end, member_name)
    if method_span:
        return method_span, "method"

    getter_span = find_method(lines, start, end, f"_get_{member_name}")
    setter_span = find_method(lines, start, end, f"_set_{member_name}")
    if getter_span or setter_span:
        spans = [span for span in (getter_span, setter_span) if span]
        return (min(span[0] for span in spans), max(span[1] for span in spans)), "property"

    return None


def find_assigned_member(
    lines: list[str], class_name: str, member_name: str
) -> tuple[int, int] | None:
    prefix = f"{class_name}.{member_name} ="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            return index, index + 1
    return None


def print_block(path: Path, lines: list[str], start: int, end: int, max_lines: int) -> None:
    print(f"# {path}:{start + 1}")
    for index in range(start, min(end, start + max_lines)):
        print(f"{index + 1:>6}: {lines[index].rstrip()}")


def lookup_symbol(files: list[Path], query: str, max_lines: int) -> bool:
    if "." not in query:
        return False

    class_name, method_name = query.split(".", 1)
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        class_span = find_class(lines, class_name)
        if not class_span:
            continue

        member = find_member(lines, class_span[0], class_span[1], method_name)
        assigned_member = find_assigned_member(lines, class_name, method_name)
        if member:
            member_span, member_kind = member
            print_block(path, lines, member_span[0], member_span[1], max_lines)
            if member_kind == "property":
                property_prefix = f"{class_name}.{method_name} = property("
                for index, line in enumerate(lines):
                    if line.startswith(property_prefix):
                        print()
                        print_block(path, lines, index, index + 1, 1)
                        break
        elif assigned_member:
            print_block(path, lines, assigned_member[0], assigned_member[1], 1)
        else:
            print_block(path, lines, class_span[0], class_span[1], max_lines)
            print(f"\n# Class found, but member '{method_name}' was not found in that class.")
        return True

    return False


def text_search(files: list[Path], query: str, context: int, limit: int) -> bool:
    needle = query.lower()
    hits = 0

    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for index, line in enumerate(lines):
            if needle not in line.lower():
                continue

            if hits:
                print()
            start = max(0, index - context)
            end = min(len(lines), index + context + 1)
            print_block(path, lines, start, end, end - start)
            hits += 1
            if hits >= limit:
                return True

    return hits > 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Search local Autodesk Fusion Python API stubs for classes, methods, and signatures."
    )
    parser.add_argument(
        "query",
        help="Search text or Class.member, e.g. TemporaryBRepManager.createSphere or BRepBody.volume",
    )
    parser.add_argument("--adsk-package", type=Path, help="Override the local adsk package directory")
    parser.add_argument("--context", type=int, default=5, help="Context lines for text search")
    parser.add_argument("--limit", type=int, default=12, help="Maximum text-search hits")
    parser.add_argument("--max-lines", type=int, default=80, help="Maximum lines for a symbol block")
    args = parser.parse_args(argv)

    adsk_package = args.adsk_package or newest_adsk_package()
    if not adsk_package or not adsk_package.exists():
        print("Could not find Autodesk Fusion's local adsk package.", file=sys.stderr)
        return 2

    files = stub_files(adsk_package)
    if lookup_symbol(files, args.query, args.max_lines):
        return 0
    if text_search(files, args.query, args.context, args.limit):
        return 0

    print(f"No local Fusion API stub matches for: {args.query}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
