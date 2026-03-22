import argparse
import asyncio
import json
import time
import urllib.request
from urllib.error import HTTPError

import websockets


def post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            return json.loads(content)
        except Exception:
            return {"ok": False, "error": f"http_{e.code}", "raw": content}


def login_and_me(http_base: str, username: str, password: str) -> tuple[str, dict]:
    login = post_json(f"{http_base}/api/login", {"username": username, "password": password})
    if not login.get("ok"):
        raise RuntimeError(f"login failed: {login}")
    token = login.get("access_token", "")
    me = post_json(
        f"{http_base}/api/me",
        {},
        headers={"Authorization": f"Bearer {token}"},
    )
    if not me.get("ok"):
        raise RuntimeError(f"/api/me failed: {me}")
    return token, me["user"]


async def collect_client_events(
    name: str,
    ws_url: str,
    token: str,
    request_id: str,
    start_event: asyncio.Event,
    timeout_s: float,
) -> dict:
    final_url = f"{ws_url}?token={token}"
    data = {"name": name, "inbound": [], "outbound": [], "duplicates": []}
    seen = set()
    started = time.time()
    async with websockets.connect(final_url) as ws:
        await start_event.wait()
        while time.time() - started < timeout_s:
            remain = max(0.1, timeout_s - (time.time() - started))
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remain)
            except asyncio.TimeoutError:
                break
            payload = json.loads(raw)
            typ = payload.get("type", "")
            if typ not in {"inbound_message", "outbound_message"}:
                continue
            metadata = payload.get("metadata", {}) or {}
            req = metadata.get("request_id") or payload.get("request_id") or ""
            if req != request_id:
                continue
            event_id = payload.get("event_id") or f"{typ}|{payload.get('channel')}|{payload.get('chat_id')}|{payload.get('content')}"
            if event_id in seen:
                data["duplicates"].append(event_id)
            seen.add(event_id)
            data["inbound" if typ == "inbound_message" else "outbound"].append(payload)
            if data["inbound"] and data["outbound"]:
                break
    return data


async def run_check(args) -> int:
    token, user = login_and_me(args.dashboard_http, args.username, args.password)
    request_id = f"e2e-{int(time.time() * 1000)}"
    start_event = asyncio.Event()
    client_tasks = [
        asyncio.create_task(
            collect_client_events("client-a", args.dashboard_ws, token, request_id, start_event, args.timeout)
        ),
        asyncio.create_task(
            collect_client_events("client-b", args.dashboard_ws, token, request_id, start_event, args.timeout)
        ),
    ]
    await asyncio.sleep(0.6)
    start_event.set()
    await asyncio.to_thread(
        post_json,
        f"{args.gateway_http}/message",
        {
            "channel": "cli",
            "sender_id": args.sender_id,
            "chat_id": args.chat_id,
            "content": f"e2e-sync-check {request_id}",
            "user_id": user["user_id"],
            "request_id": request_id,
        },
    )
    results = await asyncio.gather(*client_tasks)
    report = {
        "request_id": request_id,
        "clients": results,
        "checks": {
            "both_have_inbound": all(r["inbound"] for r in results),
            "both_have_outbound": all(r["outbound"] for r in results),
            "no_duplicates": all(not r["duplicates"] for r in results),
        },
    }
    report["checks"]["consistent_outbound_event_ids"] = (
        set(x.get("event_id") for x in results[0]["outbound"] if x.get("event_id"))
        == set(x.get("event_id") for x in results[1]["outbound"] if x.get("event_id"))
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(report["checks"].values()) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--dashboard-http", default="http://127.0.0.1:18791")
    p.add_argument("--dashboard-ws", default="ws://127.0.0.1:18792/ws")
    p.add_argument("--gateway-http", default="http://127.0.0.1:18790")
    p.add_argument("--username", default="admin")
    p.add_argument("--password", default="admin2891")
    p.add_argument("--sender-id", default="e2e-cli")
    p.add_argument("--chat-id", default="direct")
    p.add_argument("--timeout", type=float, default=15.0)
    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run_check(args)))
