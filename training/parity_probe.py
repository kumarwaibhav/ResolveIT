"""FP32 vs INT8 parity on fixed generated tickets, through the serving tokenizer path."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from training.release_bundle import feed, session, tokenizer_for  # noqa: E402

TEXTS = [
    "Outlook keeps crashing for the whole floor since this morning, urgent",
    "mera laptop bahut slow hai aur VPN bhi nahi chal raha",
    "वीपीएन सुबह से काम नहीं कर रहा, बहुत जरूरी",
    "SAP shows an error only me since yesterday",
    "I clicked a suspicious link and now my account got hacked",
    "it stopped working, please help",
    "The Jenkins pipeline is very slow again",
    "payslip khul nahi raha, jaldi dekho",
    "Incident report ab12: service: VPN; component: office gateway; symptom: connection fails",
    "projector in the conference room won't open",
    "AWS console keeps disconnecting for everyone",
    "Postgres database error 0x80070005 since 3 hours ago",
]


def main() -> int:
    bundle = ROOT / "artifacts/release_candidate_bundle"
    candidate = Path(sys.argv[1]) if len(sys.argv) > 1 else bundle / "model_int8.onnx"
    tok = tokenizer_for(bundle)
    feeds = [feed(tok, t) for t in TEXTS]
    fp32 = session(ROOT / "artifacts/training/fp32_export/model_fp32.onnx", 4)
    expected = [fp32.run(None, f) for f in feeds]
    del fp32
    q = session(candidate, 4)
    actual = [q.run(None, f) for f in feeds]
    out = {}
    for i, name in enumerate(("bio_logits", "segment_logits", "pooled")):
        d = np.concatenate([(a[i] - b[i]).ravel() for a, b in zip(expected, actual, strict=True)])
        ref = np.concatenate([a[i].ravel() for a in expected])
        out[name] = {
            "max_abs": round(float(np.abs(d).max()), 4),
            "rmse": round(float(np.sqrt((d**2).mean())), 4),
            "ref_std": round(float(ref.std()), 4),
        }
    cos = [
        float(np.dot(a[2][0], b[2][0]) / (np.linalg.norm(a[2][0]) * np.linalg.norm(b[2][0])))
        for a, b in zip(expected, actual, strict=True)
    ]
    out["pooled_cosine_min"] = round(min(cos), 4)
    out["passes_predeclared"] = all(
        v["max_abs"] <= 2 and v["rmse"] <= 0.25 for k, v in out.items() if isinstance(v, dict)
    )
    print(json.dumps({"candidate": candidate.name, **out}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
