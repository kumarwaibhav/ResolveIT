"""Stream embedded ONNX initializer bytes to external data without full graph copies.

Only top-level graph initializers are transformed. Other protobuf fields are
copied with a bounded buffer, preserving nested graphs and tensor attributes.
Original files remain untouched. ONNX checker/ORT must validate the output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

MAX_METADATA = 16 * 1024 * 1024


def varint(value: int) -> bytes:
    output = bytearray()
    while value > 127:
        output.append((value & 127) | 128)
        value >>= 7
    output.append(value)
    return bytes(output)


def read_varint(stream: BinaryIO, end: int) -> int:
    value = 0
    for shift in range(0, 70, 7):
        if stream.tell() >= end:
            raise ValueError("Truncated protobuf varint")
        chunk = stream.read(1)
        if not chunk:
            raise ValueError("Truncated protobuf varint")
        byte = chunk[0]
        if shift == 63 and byte > 1:
            raise ValueError("Oversized protobuf varint")
        value |= (byte & 127) << shift
        if not byte & 128:
            return value
    raise ValueError("Oversized protobuf varint")


def fields(stream: BinaryIO, end: int) -> Iterator[tuple[int, int, int, int, int]]:
    while stream.tell() < end:
        start = stream.tell()
        key = read_varint(stream, end)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise ValueError("Invalid protobuf field")
        if wire == 2:
            size = read_varint(stream, end)
            payload = stream.tell()
            finish = payload + size
        elif wire == 0:
            payload = stream.tell()
            read_varint(stream, end)
            finish = stream.tell()
        elif wire in (1, 5):
            payload = stream.tell()
            finish = payload + (8 if wire == 1 else 4)
        else:
            raise ValueError("Unsupported protobuf wire type")
        if finish > end:
            raise ValueError("Truncated protobuf field")
        yield number, wire, start, payload, finish
        stream.seek(finish)


def copy_bytes(source: BinaryIO, target: BinaryIO, size: int, checkpoint: Callable[[], object]) -> None:
    while size:
        chunk = source.read(min(size, 1024 * 1024))
        if not chunk:
            raise ValueError("Truncated graph during copy")
        target.write(chunk)
        size -= len(chunk)
        if target.tell() % (32 * 1024 * 1024) < len(chunk):
            checkpoint()


def tensor(
    source: BinaryIO, end: int, data: BinaryIO, location: str, checkpoint: Callable[[], object]
) -> bytes:
    import onnx

    metadata = bytearray()
    raw: tuple[int, int] | None = None
    for number, wire, start, payload, finish in fields(source, end):
        if number == 9 and wire == 2:
            if raw is not None:
                raise ValueError("Duplicate initializer raw data")
            raw = payload, finish - payload
        else:
            size = finish - start
            if len(metadata) + size > MAX_METADATA:
                raise ValueError("Initializer metadata too large")
            source.seek(start)
            metadata.extend(source.read(size))
    item = onnx.TensorProto()
    item.ParseFromString(bytes(metadata))
    if item.external_data or item.data_location == onnx.TensorProto.EXTERNAL:
        raise ValueError("Input must use embedded initializers")
    if raw is not None:
        offset = data.tell()
        source.seek(raw[0])
        copy_bytes(source, data, raw[1], checkpoint)
        item.data_location = onnx.TensorProto.EXTERNAL
        for key, value in (("location", location), ("offset", str(offset)), ("length", str(raw[1]))):
            entry = item.external_data.add()
            entry.key, entry.value = key, value
    return bytes(item.SerializeToString())


def _convert(source_path: Path, output: Path, checkpoint: Callable[[], object]) -> dict[str, object]:
    if source_path.is_symlink() or source_path.is_junction():
        raise ValueError("Input links forbidden")
    if output.exists():
        raise ValueError("Refusing to overwrite existing graph")
    output.parent.mkdir(parents=True, exist_ok=True)
    weights = output.with_suffix(".weights.bin")
    graph_tmp = output.with_suffix(".graph.tmp")
    if weights.exists() or graph_tmp.exists():
        raise ValueError("Output companion already exists")
    original = source_path.stat()
    graph_count = 0
    with source_path.open("rb") as source, weights.open("xb") as data, output.open("xb") as target:
        for number, wire, start, payload, finish in fields(source, original.st_size):
            if number != 7 or wire != 2:
                source.seek(start)
                copy_bytes(source, target, finish - start, checkpoint)
                continue
            graph_count += 1
            if graph_count != 1:
                raise ValueError("Duplicate model graph")
            source.seek(payload)
            with graph_tmp.open("xb") as graph:
                for gnum, gwire, gstart, gpayload, gfinish in fields(source, finish):
                    if gnum == 5 and gwire == 2:
                        source.seek(gpayload)
                        encoded = tensor(source, gfinish, data, weights.name, checkpoint)
                        graph.write(varint((5 << 3) | 2) + varint(len(encoded)) + encoded)
                    else:
                        source.seek(gstart)
                        copy_bytes(source, graph, gfinish - gstart, checkpoint)
            size = graph_tmp.stat().st_size
            target.write(varint((7 << 3) | 2) + varint(size))
            with graph_tmp.open("rb") as graph:
                copy_bytes(graph, target, size, checkpoint)
            graph_tmp.unlink()
    current = source_path.stat()
    if graph_count != 1 or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
        original.st_dev,
        original.st_ino,
        original.st_size,
        original.st_mtime_ns,
    ):
        raise ValueError("Missing graph or source changed")
    checkpoint()
    digest = hashlib.sha256()
    with output.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "graph_bytes": output.stat().st_size,
        "weights_bytes": weights.stat().st_size,
        "graph_sha256": digest.hexdigest(),
        "output": str(output),
    }


def convert(source_path: Path, output: Path, checkpoint: Callable[[], object]) -> dict[str, object]:
    """Stage files privately; publish graph only after the entire stream succeeds."""
    output.parent.mkdir(parents=True, exist_ok=True)
    weights = output.with_suffix(".weights.bin")
    if output.exists() or weights.exists():
        raise ValueError("Refusing to overwrite existing graph or weights")
    with tempfile.TemporaryDirectory(prefix=".externalize-", dir=output.parent) as temporary:
        stage = Path(temporary).resolve()
        if not stage.is_relative_to(output.parent.resolve()):
            raise ValueError("Temporary directory escaped output parent")
        staged_output = stage / output.name
        receipt = _convert(source_path, staged_output, checkpoint)
        if output.exists() or weights.exists():
            raise ValueError("Output changed during conversion")
        os.replace(staged_output.with_suffix(".weights.bin"), weights)
        os.replace(staged_output, output)
    receipt["output"] = str(output)
    return receipt


if __name__ == "__main__":
    from scripts.gpu_guard import ResourceGuard

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    guard = ResourceGuard()
    guard.checkpoint()
    try:
        print(json.dumps(convert(args.source, args.output, guard.checkpoint)))
    finally:
        guard.close()
