"""INT8 block-wise weight storage, dequantized once when the session loads.

Each weight MatMul B[K, N] becomes Reshape(Mul(Cast(Bq), S)) with Bq int8 [K/32, 32, N] and
S float [K/32, 1, N] (symmetric, scale = absmax/127 per 32-row block). All inputs are
initializers, so ONNX Runtime constant-folds them at load: the file ships INT8 weights,
compute is FP32 (activations never quantized, which is what broke parity before), and
there is no per-call dequantization cost (which made MatMulNBits slow on short tickets).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnx
from onnx import helper, numpy_helper

BLOCK = 32


def convert(source: Path, target: Path) -> int:
    model = onnx.load(str(source))
    graph = model.graph
    inits = {t.name: t for t in graph.initializer}
    uses: dict[str, list[tuple[str, int]]] = {}
    for node in graph.node:
        for i, name in enumerate(node.input):
            uses.setdefault(name, []).append((node.op_type, i))
    # Any 2-D weight that is the right operand of some MatMul. DeBERTa also feeds query/key
    # projections through Identity into the relative-position path; replacing the initializer
    # by a same-named node output serves every consumer the same dequantized tensor.
    eligible = {
        name
        for name, u in uses.items()
        if name in inits
        and any(op == "MatMul" and i == 1 for op, i in u)
        and len(inits[name].dims) == 2
        and inits[name].dims[0] % BLOCK == 0
    }
    new_nodes = []
    done: set[str] = set()
    converted = 0
    for node in graph.node:
        for weight in [x for x in node.input if x in eligible and x not in done]:
            tensor = inits[weight]
            w = numpy_helper.to_array(tensor).astype(np.float32)
            k, n = w.shape
            blocks = w.reshape(k // BLOCK, BLOCK, n)
            scale = np.abs(blocks).max(axis=1, keepdims=True) / 127.0
            scale[scale == 0] = 1.0
            q = np.clip(np.rint(blocks / scale), -127, 127).astype(np.int8)
            base = f"{weight}_bq"
            graph.initializer.remove(tensor)
            graph.initializer.extend(
                [
                    numpy_helper.from_array(q, f"{base}_int8"),
                    numpy_helper.from_array(scale.astype(np.float32), f"{base}_scale"),
                    numpy_helper.from_array(np.array([k, n], dtype=np.int64), f"{base}_shape"),
                ]
            )
            new_nodes += [
                helper.make_node("Cast", [f"{base}_int8"], [f"{base}_f"], to=onnx.TensorProto.FLOAT),
                helper.make_node("Mul", [f"{base}_f", f"{base}_scale"], [f"{base}_deq"]),
                helper.make_node("Reshape", [f"{base}_deq", f"{base}_shape"], [weight]),
            ]
            done.add(weight)
            converted += 1
        new_nodes.append(node)
    del graph.node[:]
    graph.node.extend(new_nodes)
    converted += quantize_embedding(graph)
    onnx.save(model, str(target))
    onnx.checker.check_model(str(target))
    return converted


def quantize_embedding(graph: onnx.GraphProto) -> int:
    """Word-embedding table as INT8 rows (block 32 along hidden); only gathered rows are dequantized.

    Gather(table, ids) -> Reshape(Mul(Cast(Gather(q, ids)), Gather(s, ids)), [*ids.shape, H]).
    Saves ~0.6 GB of resident memory: the table is never expanded to FP32 as a whole.
    """
    inits = {t.name: t for t in graph.initializer}
    uses: dict[str, list[onnx.NodeProto]] = {}
    for node in graph.node:
        for name in node.input:
            uses.setdefault(name, []).append(node)
    done = 0
    for name, tensor in list(inits.items()):
        nodes = uses.get(name, [])
        if len(tensor.dims) != 2 or tensor.dims[0] < 100_000 or tensor.dims[1] % BLOCK:
            continue
        if not nodes or any(n.op_type != "Gather" or n.input[0] != name for n in nodes):
            continue
        table = numpy_helper.to_array(tensor).astype(np.float32, copy=False)
        v, h = table.shape
        graph.initializer.remove(tensor)
        del tensor
        q = np.empty((v, h // BLOCK, BLOCK), dtype=np.int8)
        scale = np.empty((v, h // BLOCK, 1), dtype=np.float32)
        for start in range(0, v, 16_384):  # row chunks keep temporaries small (laptop memory)
            blocks = table[start : start + 16_384].reshape(-1, h // BLOCK, BLOCK)
            chunk_scale = np.abs(blocks).max(axis=2, keepdims=True) / 127.0
            chunk_scale[chunk_scale == 0] = 1.0
            scale[start : start + 16_384] = chunk_scale
            q[start : start + 16_384] = np.clip(np.rint(blocks / chunk_scale), -127, 127)
        del table
        graph.initializer.extend(
            [
                numpy_helper.from_array(q, f"{name}_eq_int8"),
                numpy_helper.from_array(scale.astype(np.float32), f"{name}_eq_scale"),
                numpy_helper.from_array(np.array([h], dtype=np.int64), f"{name}_eq_hidden"),
            ]
        )
        rebuilt: list[onnx.NodeProto] = []
        for i, node in enumerate(graph.node):
            if node in nodes:
                ids, out, p = node.input[1], node.output[0], f"{name}_eq{i}"
                rebuilt += [
                    helper.make_node("Gather", [f"{name}_eq_int8", ids], [f"{p}_q"], axis=0),
                    helper.make_node("Gather", [f"{name}_eq_scale", ids], [f"{p}_s"], axis=0),
                    helper.make_node("Cast", [f"{p}_q"], [f"{p}_f"], to=onnx.TensorProto.FLOAT),
                    helper.make_node("Mul", [f"{p}_f", f"{p}_s"], [f"{p}_m"]),
                    helper.make_node("Shape", [ids], [f"{p}_ids_shape"]),
                    helper.make_node(
                        "Concat", [f"{p}_ids_shape", f"{name}_eq_hidden"], [f"{p}_shape"], axis=0
                    ),
                    helper.make_node("Reshape", [f"{p}_m", f"{p}_shape"], [out]),
                ]
            else:
                rebuilt.append(node)
        del graph.node[:]
        graph.node.extend(rebuilt)
        done += 1
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fp32", type=Path)
    parser.add_argument("int8", type=Path)
    args = parser.parse_args()
    print({"converted_matmuls": convert(args.fp32, args.int8)}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
