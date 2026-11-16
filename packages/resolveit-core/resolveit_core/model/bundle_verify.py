"""Validate immutable bundle files against a manifest; hashes do not authenticate a publisher.

Pin --expected-id from a trusted release channel. This auditor never enables
production routing. Loaders must consume the verified immutable release directory,
not reopen mutable paths after this check.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any

HEX = re.compile(r"^[0-9a-f]{64}$")
REQUIRED = {"model_int8.onnx", "calibration.json", "report.json"}
MAX_FILE_BYTES = 2 * 1024**3


class BundleError(ValueError):
    """Untrusted or inconsistent artifact."""


def no_links(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise BundleError("Links and junctions are forbidden")


def read_file(path: Path, limit: int) -> bytes:
    no_links(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise BundleError("Artifact must be a bounded regular file")
        content = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        current = path.stat(follow_symlinks=False)
        no_links(path)
        if (
            len(content) > limit
            or (before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_ino, after.st_size, after.st_mtime_ns)
            or (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino)
        ):
            raise BundleError("Artifact changed during verification")
        return content


def json_object(content: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise BundleError("Duplicate JSON key")
            result[key] = value
        return result

    value = json.loads(content, object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise BundleError("JSON object required")
    return value


def file_digest(path: Path) -> str:
    no_links(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
            raise BundleError("Artifact must be a bounded regular file")
        digest = hashlib.sha256()
        size = 0
        while block := stream.read(65536):
            size += len(block)
            if size > MAX_FILE_BYTES:
                raise BundleError("Artifact exceeds size bound")
            digest.update(block)
        after = os.fstat(stream.fileno())
        current = path.stat(follow_symlinks=False)
        no_links(path)
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino):
            raise BundleError("Artifact changed during verification")
        return digest.hexdigest()


def verify_bundle(directory: Path, expected_id: str | None = None) -> dict[str, Any]:
    no_links(directory.absolute())
    root = directory.resolve(strict=True)
    manifest = json_object(read_file(root / "manifest.json", 1024**2))
    files = manifest.get("files")
    if not isinstance(files, dict) or not files.keys() >= REQUIRED or len(files) > 256:
        raise BundleError("Required artifact set missing or excessive")
    if not isinstance(manifest.get("bundle_id"), str) or not HEX.fullmatch(manifest["bundle_id"]):
        raise BundleError("Invalid bundle identity")
    if expected_id is not None and manifest["bundle_id"] != expected_id:
        raise BundleError("Bundle does not match trusted identity")
    metadata_files: dict[str, dict[str, Any]] = {}
    for name, digest in files.items():
        if not isinstance(name, str) or not name or any(c in name for c in ("\\", ":", "\0")):
            raise BundleError("Unsafe artifact path")
        parts = name.split("/")
        if any(part in {"", ".", ".."} for part in parts) or PurePosixPath(name).is_absolute():
            raise BundleError("Unsafe artifact path")
        if not isinstance(digest, str) or not HEX.fullmatch(digest):
            raise BundleError("Invalid artifact digest")
        path = root.joinpath(*parts)
        no_links(path)
        if not path.resolve(strict=True).is_relative_to(root):
            raise BundleError("Artifact escaped bundle directory")
        if name in {"calibration.json", "report.json"}:
            content = read_file(path, 1024**2)
            actual_digest = hashlib.sha256(content).hexdigest()
            metadata_files[name] = json_object(content)
        else:
            actual_digest = file_digest(path)
        if actual_digest != digest:
            raise BundleError("Artifact digest mismatch")
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != manifest["bundle_id"]:
        raise BundleError("Manifest identity mismatch")
    source = manifest.get("label_source")
    eligible = manifest.get("production_eligible")
    if source not in {"synthetic_seed", "llm_silver", "human_gold"} or type(eligible) is not bool:
        raise BundleError("Explicit provenance and eligibility required")
    if source != "human_gold" and eligible:
        raise BundleError("Non-gold bundle cannot claim production eligibility")
    for name in ("calibration.json", "report.json"):
        metadata = metadata_files[name]
        if metadata.get("label_source") != source or metadata.get("production_eligible") is not eligible:
            raise BundleError("Artifact provenance mismatch")
    return {
        "bundle_id": manifest["bundle_id"],
        "verified_files": len(files),
        "label_source": source,
        "publisher_authenticated": expected_id is not None,
        "production_authorized": False,
    }


def read_verified(directory: Path, expected_id: str, names: tuple[str, ...]) -> dict[str, bytes]:
    """Read each named artifact into memory once and check it against the pinned identity.

    Loaders must build from these bytes, never by reopening paths: whatever is on disk
    after this call does not matter, which closes the verify-then-load (TOCTOU) window.
    Every requested name must be listed in the manifest.
    """
    if not HEX.fullmatch(expected_id):
        raise BundleError("A pinned bundle identity is required")
    no_links(directory.absolute())
    root = directory.resolve(strict=True)
    manifest = json_object(read_file(root / "manifest.json", 1024**2))
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise BundleError("Required artifact set missing or excessive")
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != expected_id or manifest.get("bundle_id") != expected_id:
        raise BundleError("Bundle does not match trusted identity")
    out: dict[str, bytes] = {}
    for name in names:
        digest = files.get(name)
        if not isinstance(digest, str) or not HEX.fullmatch(digest):
            raise BundleError("Artifact required by the loader is not in the manifest")
        path = root.joinpath(*name.split("/"))
        no_links(path)
        if not path.resolve(strict=True).is_relative_to(root):
            raise BundleError("Artifact escaped bundle directory")
        content = read_file(path, MAX_FILE_BYTES)
        if hashlib.sha256(content).hexdigest() != digest:
            raise BundleError("Artifact digest mismatch")
        out[name] = content
    return out


__all__ = [
    "HEX",
    "MAX_FILE_BYTES",
    "REQUIRED",
    "BundleError",
    "file_digest",
    "json_object",
    "no_links",
    "read_file",
    "read_verified",
    "verify_bundle",
]
