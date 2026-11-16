from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_bundle import BundleError, verify_bundle


def make_bundle(root: Path) -> dict[str, Any]:
    metadata = {"label_source": "synthetic_seed", "production_eligible": False}
    (root / "model_int8.onnx").write_bytes(b"fixture model bytes, not an ONNX validity test")
    for name in ("calibration.json", "report.json"):
        (root / name).write_text(json.dumps(metadata))
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
    manifest = {
        **metadata,
        "files": files,
        "bundle_id": hashlib.sha256(
            json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    save(root, manifest)
    return manifest


def save(root: Path, manifest: dict[str, Any]) -> None:
    (root / "manifest.json").write_text(json.dumps(manifest))


def test_valid_bundle_requires_trusted_identity_for_publisher(tmp_path: Path) -> None:
    manifest = make_bundle(tmp_path)
    result = verify_bundle(tmp_path)
    assert result["verified_files"] == 3 and result["production_authorized"] is False
    assert result["publisher_authenticated"] is False
    assert verify_bundle(tmp_path, manifest["bundle_id"])["publisher_authenticated"] is True
    with pytest.raises(BundleError, match="trusted identity"):
        verify_bundle(tmp_path, "0" * 64)


@pytest.mark.parametrize("name", ["../outside", "/absolute", "a/../b", "a//b", "a\\b", "C:outside"])
def test_path_escape_rejected(tmp_path: Path, name: str) -> None:
    manifest = make_bundle(tmp_path)
    manifest["files"][name] = "0" * 64
    save(tmp_path, manifest)
    with pytest.raises(BundleError, match="Unsafe artifact path"):
        verify_bundle(tmp_path)


def test_tampering_and_missing_artifact_rejected(tmp_path: Path) -> None:
    make_bundle(tmp_path)
    model = tmp_path / "model_int8.onnx"
    model.write_bytes(b"changed")
    with pytest.raises(BundleError, match="digest mismatch"):
        verify_bundle(tmp_path)
    model.unlink()
    with pytest.raises(OSError):
        verify_bundle(tmp_path)


def test_duplicate_manifest_keys_rejected(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text('{"files":{},"files":{}}')
    with pytest.raises(BundleError, match="Duplicate"):
        verify_bundle(tmp_path)


def test_synthetic_cannot_claim_production(tmp_path: Path) -> None:
    manifest = make_bundle(tmp_path)
    manifest["production_eligible"] = True
    save(tmp_path, manifest)
    with pytest.raises(BundleError, match="Non-gold"):
        verify_bundle(tmp_path)


def test_metadata_provenance_must_match_even_with_valid_hashes(tmp_path: Path) -> None:
    manifest = make_bundle(tmp_path)
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"label_source": "human_gold", "production_eligible": False}))
    manifest["files"]["report.json"] = hashlib.sha256(report.read_bytes()).hexdigest()
    manifest["bundle_id"] = hashlib.sha256(
        json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    save(tmp_path, manifest)
    with pytest.raises(BundleError, match="provenance mismatch"):
        verify_bundle(tmp_path)


def test_symlink_rejected(tmp_path: Path) -> None:
    make_bundle(tmp_path)
    model = tmp_path / "model_int8.onnx"
    real = tmp_path / "real_model"
    model.rename(real)
    try:
        model.symlink_to(real)
    except OSError:
        pytest.skip("OS lacks symlink privilege")
    with pytest.raises(BundleError, match="Links"):
        verify_bundle(tmp_path)
