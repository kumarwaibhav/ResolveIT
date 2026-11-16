"""Audit release hygiene, implementation completeness and the core license boundary."""

from __future__ import annotations

import ast
import io
import json
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHOR = "Kumar Waibhav Akshat <kwa.waibhav@gmail.com>"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def audit() -> dict[str, object]:
    errors: list[str] = []
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
    count = 0
    for name in sorted(set(paths)):
        path = ROOT / name
        if not name or path.suffix != ".py" or not path.is_file():
            continue
        count += 1
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=name)
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and "TODO" in token.string:
                errors.append(f"{name}:{token.start[0]} unfinished comment")
        # Typing Protocol members are declarations by definition; `...` bodies there are not stubs.
        protocol_members = {
            id(item)
            for cls in ast.walk(tree)
            if isinstance(cls, ast.ClassDef)
            and any(
                (isinstance(b, ast.Name) and b.id == "Protocol")
                or (isinstance(b, ast.Attribute) and b.attr == "Protocol")
                for b in cls.bases
            )
            for item in cls.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Pass):
                errors.append(f"{name}:{node.lineno} empty statement")
            if isinstance(node, ast.Raise) and node.exc is not None:
                target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                if isinstance(target, ast.Name) and target.id == "NotImplementedError":
                    errors.append(f"{name}:{node.lineno} unimplemented behavior")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and id(node) not in protocol_members:
                body = [
                    item
                    for item in node.body
                    if not (
                        isinstance(item, ast.Expr)
                        and isinstance(item.value, ast.Constant)
                        and isinstance(item.value.value, str)
                    )
                ]
                if not body or all(
                    isinstance(item, ast.Expr)
                    and isinstance(item.value, ast.Constant)
                    and item.value.value is Ellipsis
                    for item in body
                ):
                    errors.append(f"{name}:{node.lineno} function stub")
            if name.replace("\\", "/").startswith("packages/resolveit-core/resolveit_core/"):
                modules = (
                    [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                if isinstance(node, ast.Call) and (
                    (isinstance(node.func, ast.Name) and node.func.id in {"__import__", "import_module"})
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                ):
                    candidates = [
                        *node.args[:1],
                        *[item.value for item in node.keywords if item.arg == "name"],
                    ]
                    modules.extend(
                        item.value
                        for item in candidates
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    )
                if any(module.split(".")[0] in {"enterprise", "resolveit_enterprise"} for module in modules):
                    errors.append(
                        f"{name}:{getattr(node, 'lineno', 0)} enterprise import across core boundary"
                    )
    license_text = (ROOT / "packages/resolveit-core/LICENSE").read_text()
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        errors.append("core Apache-2.0 license missing")
    configured = (
        f"{git('config', '--local', 'user.name').strip()} <{git('config', '--local', 'user.email').strip()}>"
    )
    if configured != AUTHOR:
        errors.append("local author differs from owner-authorized identity")
    if "co-authored-by:" in git("log", "--format=%B").lower():
        errors.append("co-author trailer requires review")
    if git("status", "--porcelain").strip():
        errors.append("working tree is not clean")
    if (
        not (ROOT / ".githooks/pre-commit").is_file()
        or git("config", "--local", "core.hooksPath").strip() != ".githooks"
    ):
        errors.append("secret pre-commit hook is not installed")
    return {"python_files": count, "errors": errors, "passed": not errors}


if __name__ == "__main__":
    receipt = audit()
    print(json.dumps(receipt, indent=2))
    sys.exit(0 if receipt["passed"] else 1)
