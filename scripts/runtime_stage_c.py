"""Sequential guarded native production runtime verification; synthetic data only."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import importlib.util
import json
import os
import secrets
import subprocess
import sys
import time
from uuid import uuid4

import asyncpg
import httpx
import numpy as np
from dev_native import ROOT, environment, prepare
from gpu_guard import stop_tree

OUT = ROOT / "artifacts/stage-c"


async def reviewers(env: dict[str, str]) -> list[str]:
    conn = await asyncpg.connect(
        env["RESOLVEIT_MIGRATOR_DATABASE_URL"].replace("postgresql+asyncpg", "postgresql")
    )
    keys = [f"rit_{secrets.token_urlsafe(32)}" for _ in range(2)]
    async with conn.transaction():
        await conn.execute(
            "SELECT set_config('app.current_tenant_id',$1,true)", "00000000-0000-4000-8000-000000000001"
        )
        for key in keys:
            await conn.execute(
                "INSERT INTO api_keys(id,tenant_id,key_hash,role,human_subject_id) "
                "VALUES($1,$2,$3,'reviewer',$4)",
                uuid4(),
                __import__("uuid").UUID("00000000-0000-4000-8000-000000000001"),
                hashlib.sha256(key.encode()).hexdigest(),
                uuid4(),
            )
    await conn.close()
    return keys


def wait_url(url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Owned runtime process exited before readiness")
        with contextlib.suppress(httpx.HTTPError):
            if httpx.get(url, timeout=3).status_code == 200:
                return
        time.sleep(0.5)
    raise RuntimeError("Loopback readiness deadline")


def mrtr(client: httpx.Client) -> dict[str, object]:
    headers = {
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/call",
        "Mcp-Name": "submit_incident",
    }
    meta = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {"elicitation": {}},
        "io.modelcontextprotocol/clientInfo": {"name": "stage-c", "version": "1"},
    }
    for number in range(250):
        arguments = {
            "text": "my v-p-n client says nothing, it stopped working this morning "
            f"[stage-c-{number}-{uuid4()}]"
        }
        params: dict[str, object] = {"name": "submit_incident", "arguments": arguments, "_meta": meta}
        body = {"jsonrpc": "2.0", "id": number, "method": "tools/call", "params": params}
        result = client.post("/mcp", json=body, headers=headers).json()["result"]
        if result["resultType"] != "input_required":
            continue
        params.update(
            {
                "requestState": result["requestState"],
                "inputResponses": {
                    "clarify": {
                        "action": "accept",
                        "content": {"answer": "vpn", "evidence_quote": "v-p-n client"},
                    }
                },
            }
        )
        answer = client.post("/mcp", json=body, headers=headers).json()["result"]
        assert answer["resultType"] == "complete"
        assert answer["structuredContent"]["incident"]["state"] == "DEFERRED"
        assert (
            client.post("/mcp", json=body, headers=headers).json()["result"]["structuredContent"]["incident"][
                "id"
            ]
            == answer["structuredContent"]["incident"]["id"]
        )
        return {
            "roundtrips": 2,
            "attempts_until_exploration": number + 1,
            "citation": "accepted",
            "post_answer": "uncertified_defer",
            "replay": "idempotent",
        }
    raise AssertionError("No deterministic exploration incident in bounded live requests")


def timings(client: httpx.Client) -> dict[str, object]:
    def describe(values: list[float]) -> dict[str, float]:
        return {
            "p50_ms": float(np.percentile(values, 50)),
            "p95_ms": float(np.percentile(values, 95)),
            "n": len(values),
        }

    first = time.perf_counter()
    result = client.post(
        "/v1/incidents", json={"text": "database is down for the whole floor", "locale": "en"}
    )
    result.raise_for_status()
    cold = (time.perf_counter() - first) * 1000
    values = []
    for _ in range(30):
        start = time.perf_counter()
        client.post(
            "/v1/incidents", json={"text": "database is down for the whole floor", "locale": "en"}
        ).raise_for_status()
        values.append((time.perf_counter() - start) * 1000)
    import onnxruntime as ort  # type: ignore[import-untyped]

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    start = time.perf_counter()
    session = ort.InferenceSession(
        str(ROOT / "artifacts/ml-smoke/model_int8.onnx"),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    x = np.zeros((1, 32), dtype=np.float32)
    session.run(None, {"features": x})
    cold_onnx = (time.perf_counter() - start) * 1000
    for _ in range(200):
        session.run(None, {"features": x})
    onnx = []
    for _ in range(200):
        start = time.perf_counter()
        session.run(None, {"features": x})
        onnx.append((time.perf_counter() - start) * 1000)
    return {
        "api_first_incident_ms": cold,
        "api_warm_incident": describe(values),
        "onnx_load_and_first_ms": cold_onnx,
        "onnx_warm": describe(onnx),
        "onnx_provenance": "synthetic_fixture_not_pretrained",
    }


def main() -> int:
    env = environment()
    OUT.mkdir(parents=True, exist_ok=True)
    processes: list[subprocess.Popen[bytes]] = []
    logs = []
    receipt: dict[str, object] = {"provenance": "synthetic_seed", "production_authorized": False}
    try:
        asyncio.run(prepare(env))
        keys = asyncio.run(reviewers(env))
        commands = [
            (
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "resolveit_api.main:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--workers",
                    "1",
                    "--no-access-log",
                ],
                ROOT,
            ),
            ([sys.executable, "-m", "resolveit_worker.runner"], ROOT),
            (
                ["node", "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "-p", "3000"],
                ROOT / "apps/web",
            ),
        ]
        for index, (command, cwd) in enumerate(commands):
            log = (ROOT / ".runtime" / f"stage-c-{index}.log").open("wb")
            logs.append(log)
            processes.append(
                subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
            )
        wait_url("http://127.0.0.1:8000/healthz", processes[0])
        wait_url("http://127.0.0.1:3000", processes[2])
        with httpx.Client(
            base_url=env["RESOLVEIT_API_URL"],
            headers={"Authorization": f"Bearer {env['RESOLVEIT_API_KEY']}"},
            timeout=30,
        ) as client:
            receipt["latency"] = timings(client)
        probe = httpx.post(
            "http://127.0.0.1:3000/api/incidents",
            headers={"Origin": "http://127.0.0.1:3000"},
            json={"text": "database down [synthetic browser ingress probe]"},
            timeout=30,
        )
        if not probe.is_success:
            raise RuntimeError(f"Browser ingress rejected: {probe.status_code} {probe.json().get('detail')}")
        os.environ.update(env)
        from security_gate import sdk_smoke

        asyncio.run(sdk_smoke())
        receipt["official_sdk"] = "passed"
        with httpx.Client(
            base_url=env["RESOLVEIT_API_URL"],
            headers={"Authorization": f"Bearer {env['RESOLVEIT_API_KEY']}"},
            timeout=30,
        ) as client:
            receipt["mrtr"] = mrtr(client)
            incident = client.post(
                "/v1/incidents", json={"text": "database is down [synthetic dual annotation]"}
            ).json()["id"]
        spec = importlib.util.spec_from_file_location("stage_c_browser", ROOT / "apps/web/e2e/stage_c.py")
        assert spec and spec.loader
        browser = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(browser)
        receipt["browser"] = browser.run(env, keys, incident, OUT)
        receipt["status"] = "passed"
        print("Stage C SDK, MRTR, browsers and latency passed; credentials withheld.")
        return 0
    finally:
        for child in reversed(processes):
            stop_tree(child)
        for log in logs:
            log.close()
        (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
