from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import pytest
from onnx import TensorProto, helper, numpy_helper

from training.externalize_graph import convert, varint


def test_streamed_external_weights_preserve_actual_inference(tmp_path: Path) -> None:
    initial = numpy_helper.from_array(np.arange(6, dtype=np.float32).reshape(2, 3), "weight")
    graph = helper.make_graph(
        [helper.make_node("MatMul", ["x", "weight"], ["y"])],
        "tiny",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 2])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 3])],
        [initial],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=9)
    original, output = tmp_path / "original.onnx", tmp_path / "external.onnx"
    onnx.save(model, original)
    opaque = varint((1000 << 3) | 2) + varint(6) + b"opaque"
    with original.open("ab") as stream:
        stream.write(opaque)
    receipt = convert(original, output, lambda: None)
    assert receipt["weights_bytes"] == 24
    assert output.read_bytes().endswith(opaque)
    onnx.checker.check_model(str(output))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    for path in (original, output):
        session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        np.testing.assert_equal(session.run(None, {"x": np.ones((1, 2), dtype=np.float32)})[0], [[3, 5, 7]])
    with pytest.raises(ValueError, match="overwrite"):
        convert(original, output, lambda: None)


def test_truncated_graph_rejected(tmp_path: Path) -> None:
    source = tmp_path / "broken.onnx"
    source.write_bytes(b"\x3a\x7f\x00")
    with pytest.raises(ValueError, match="Truncated"):
        convert(source, tmp_path / "output.onnx", lambda: None)
    assert not (tmp_path / "output.onnx").exists()
    assert not (tmp_path / "output.weights.bin").exists()


def test_interrupted_conversion_never_publishes_graph(tmp_path: Path) -> None:
    model = helper.make_model(helper.make_graph([], "empty", [], []))
    source = tmp_path / "source.onnx"
    onnx.save(model, source)

    def stop() -> None:
        raise RuntimeError("injected interruption")

    with pytest.raises(RuntimeError, match="interruption"):
        convert(source, tmp_path / "new.onnx", stop)
    assert not (tmp_path / "new.onnx").exists()
