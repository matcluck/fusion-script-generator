#!/usr/bin/env python3
"""Statically validate a generated Autodesk Fusion Python script."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import fusion_api_lookup


RETIRED_CALLS = {
    "createInput2": "Use SketchTexts.createInput3(expression, ValueInput).",
    "setDistanceExtent": "Use setOneSideExtent or setSymmetricExtent.",
    "createThreadInfo": "Use the static ThreadInfo.create method.",
}


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    line: int | None = None


def _resolve_script(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_file():
        return path
    if not path.is_dir():
        raise FileNotFoundError(path)

    expected = path / f"{path.name}.py"
    if expected.exists():
        return expected

    scripts = sorted(path.glob("*.py"))
    if len(scripts) == 1:
        return scripts[0]
    raise RuntimeError(f"Could not select one Fusion script from {path}")


def _attribute_chain(node: ast.AST) -> list[str] | None:
    names: list[str] = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    names.append(node.id)
    names.reverse()
    return names


def _load_stub_index() -> tuple[Path | None, dict[str, tuple[Path, list[str]]]]:
    package = fusion_api_lookup.newest_adsk_package()
    if not package:
        return None, {}

    result: dict[str, tuple[Path, list[str]]] = {}
    for namespace in ("core", "fusion", "cam"):
        path = package / f"{namespace}.py"
        if not path.exists():
            continue
        result[namespace] = (
            path,
            path.read_text(encoding="utf-8", errors="replace").splitlines(),
        )
    return package, result


def _validate_static_symbol(
    chain: list[str],
    node: ast.AST,
    stubs: dict[str, tuple[Path, list[str]]],
    issues: list[Issue],
) -> None:
    if len(chain) != 4 or chain[0] != "adsk" or chain[1] not in stubs:
        return

    namespace, class_name, member_name = chain[1], chain[2], chain[3]
    _, lines = stubs[namespace]
    class_span = fusion_api_lookup.find_class(lines, class_name)
    if not class_span:
        issues.append(
            Issue(
                "error",
                "unknown-api-class",
                f"Installed Fusion stubs do not expose adsk.{namespace}.{class_name}.",
                getattr(node, "lineno", None),
            )
        )
        return

    if not fusion_api_lookup.find_member(
        lines, class_span[0], class_span[1], member_name
    ) and not fusion_api_lookup.find_assigned_member(lines, class_name, member_name):
        issues.append(
            Issue(
                "error",
                "unknown-api-member",
                f"Installed Fusion stubs do not expose {class_name}.{member_name}.",
                getattr(node, "lineno", None),
            )
        )


def _validate_manifest(
    script: Path, issues: list[Issue]
) -> tuple[Path, dict[str, object]]:
    manifest = script.with_suffix(".manifest")
    if not manifest.exists():
        issues.append(Issue("error", "missing-manifest", f"Missing {manifest.name}."))
        return manifest, {}

    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        issues.append(Issue("error", "invalid-manifest", str(error)))
        return manifest, {}

    for key in ("autodeskProduct", "type", "id", "supportedOS"):
        if key not in data:
            issues.append(Issue("error", "manifest-field", f"Manifest is missing '{key}'."))

    if data.get("type") not in ("script", "addin"):
        issues.append(
            Issue("error", "manifest-type", "Manifest type must be 'script' or 'addin'.")
        )
    if data.get("id") and data["id"] != script.stem:
        issues.append(
            Issue(
                "warning",
                "manifest-id",
                f"Manifest id '{data['id']}' does not match script name '{script.stem}'.",
            )
        )
    if script.parent.name != script.stem:
        issues.append(
            Issue(
                "warning",
                "folder-name",
                "Fusion script folder and Python filename should have the same name.",
            )
        )
    return manifest, data


def validate(script_path: Path) -> dict[str, object]:
    issues: list[Issue] = []
    script = _resolve_script(script_path)
    manifest, manifest_data = _validate_manifest(script, issues)
    package, stubs = _load_stub_index()
    if not package:
        issues.append(
            Issue(
                "warning",
                "missing-stubs",
                "Could not find local Autodesk Python stubs; API symbol checks were skipped.",
            )
        )

    try:
        source = script.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(script))
        compile(tree, str(script), "exec")
    except (OSError, SyntaxError) as error:
        issues.append(
            Issue(
                "error",
                "python-syntax",
                str(error),
                getattr(error, "lineno", None),
            )
        )
        tree = None
        source = ""

    if tree:
        top_level_functions = {
            node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if "run" not in top_level_functions:
            issues.append(Issue("error", "missing-run", "Script has no top-level run(context)."))

        build_spec_node = None
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "BUILD_SPEC" for target in targets):
                build_spec_node = node.value
                break

        if manifest_data.get("type") == "script" and build_spec_node is None:
            issues.append(
                Issue(
                    "warning",
                    "missing-build-spec",
                    "Add BUILD_SPEC with printable body names, expected count, units, and coordinate system.",
                )
            )
        elif build_spec_node is not None:
            try:
                build_spec = ast.literal_eval(build_spec_node)
                if not isinstance(build_spec, dict):
                    raise ValueError("BUILD_SPEC is not a dictionary")
                for key in (
                    "units",
                    "coordinate_system",
                    "generated_body_prefixes",
                    "printable_body_names",
                    "expected_printable_body_count",
                ):
                    if key not in build_spec:
                        issues.append(
                            Issue(
                                "warning",
                                "build-spec-field",
                                f"BUILD_SPEC is missing '{key}'.",
                                getattr(build_spec_node, "lineno", None),
                            )
                        )
            except (ValueError, SyntaxError):
                issues.append(
                    Issue(
                        "warning",
                        "dynamic-build-spec",
                        "BUILD_SPEC is not a literal dictionary, so preflight cannot inspect it.",
                        getattr(build_spec_node, "lineno", None),
                    )
                )

        imports_adsk = any(
            (
                isinstance(node, ast.Import)
                and any(alias.name == "adsk" or alias.name.startswith("adsk.") for alias in node.names)
            )
            or (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("adsk"))
            for node in tree.body
        )
        if not imports_adsk:
            issues.append(Issue("error", "missing-adsk", "Script does not import Autodesk adsk APIs."))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            chain = _attribute_chain(node.func)
            if not chain:
                continue

            member = chain[-1]
            if member in RETIRED_CALLS:
                issues.append(
                    Issue(
                        "error",
                        "retired-api",
                        f"{member} is retired. {RETIRED_CALLS[member]}",
                        node.lineno,
                    )
                )
            if member == "addNewComponent":
                issues.append(
                    Issue(
                        "warning",
                        "part-design-component",
                        "addNewComponent can fail in Part Design documents; prefer named root bodies.",
                        node.lineno,
                    )
                )
            if member == "createByReal" and node.args:
                value = node.args[0]
                if isinstance(value, ast.Constant) and isinstance(value.value, int):
                    issues.append(
                        Issue(
                            "warning",
                            "integer-real",
                            "Pass a float to ValueInput.createByReal, for example 1.0.",
                            node.lineno,
                        )
                    )
            if member == "createInput3" and node.args:
                expression = node.args[0]
                if (
                    isinstance(expression, ast.Constant)
                    and isinstance(expression.value, str)
                    and not (
                        expression.value.startswith("'")
                        and expression.value.endswith("'")
                    )
                ):
                    issues.append(
                        Issue(
                            "warning",
                            "text-expression",
                            "createInput3 literal text must be a quoted Fusion expression, e.g. \"'TEXT'\".",
                            node.lineno,
                        )
                    )

            _validate_static_symbol(chain, node, stubs, issues)

    errors = [asdict(issue) for issue in issues if issue.severity == "error"]
    warnings = [asdict(issue) for issue in issues if issue.severity == "warning"]
    return {
        "ok": not errors,
        "script": str(script),
        "manifest": str(manifest),
        "installed_adsk_package": str(package) if package else None,
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Fusion script .py file or matching folder")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        result = validate(args.path)
    except Exception as error:
        result = {
            "ok": False,
            "script": str(args.path),
            "manifest": None,
            "installed_adsk_package": None,
            "errors": [
                asdict(Issue("error", "preflight-failure", f"{type(error).__name__}: {error}"))
            ],
            "warnings": [],
        }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Fusion preflight: {'PASS' if result['ok'] else 'FAIL'}")
        print(result["script"])
        for issue in [*result["errors"], *result["warnings"]]:
            location = f" line {issue['line']}" if issue.get("line") else ""
            print(f"[{issue['severity'].upper()}] {issue['code']}{location}: {issue['message']}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
