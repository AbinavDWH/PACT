"""Demo pre-flight. Run this before recording or presenting.

Every check hits the running system rather than reading configuration, because
the failures that ruin a demo are the ones that look fine in a config file:

  - fixtures seeded 1,500 km away, so `$geoNear` returns nothing and the
    pipeline quietly runs on hardcoded candidates
  - Mongo "configured" but not connected
  - a Groq token budget already spent, so every agent silently degrades
  - the backend bound to 127.0.0.1, so the phone cannot reach it

Usage:
    python scripts/preflight.py                       # localhost, default creds
    python scripts/preflight.py --lat 13.008 --lon 80.006
    python scripts/preflight.py --base http://192.168.1.6:8000

Exit code 0 means safe to record. Non-zero means fix something first.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"

results: list[tuple[str, str, str]] = []


def record(level: str, name: str, detail: str = "") -> None:
    results.append((level, name, detail))
    icon = {PASS: "  ok  ", FAIL: " FAIL ", WARN: " warn "}[level]
    print(f"[{icon}] {name}" + (f"\n         {detail}" if detail else ""))


def call(base: str, path: str, method: str = "GET", body: dict | None = None,
         token: str | None = None, timeout: float = 10.0):
    req = urllib.request.Request(base + path, method=method)
    req.add_header("Accept", "application/json")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, data, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def haversine_km(a, b):
    import math
    r = 6371.0088
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="pact-admin")
    ap.add_argument("--org-user", default="sanjeevani")
    ap.add_argument("--org-password", default="pact-org")
    ap.add_argument("--lat", type=float, help="where the demo happens")
    ap.add_argument("--lon", type=float)
    ap.add_argument("--no-run", action="store_true",
                    help="skip the live pipeline run (saves Groq tokens)")
    args = ap.parse_args()

    print(f"\nPACT pre-flight against {args.base}\n" + "-" * 62)

    # -- 1. reachable ------------------------------------------------------
    try:
        health = call(args.base, "/api/v1/health")
    except Exception as e:
        record(FAIL, "backend reachable", f"{e}\n         start it with --host 0.0.0.0")
        return summarise()
    record(PASS, "backend reachable", f"version {health.get('version')}")

    # -- 2. mongo actually connected, not merely configured -----------------
    m = health.get("mongo", {})
    if m.get("connected"):
        record(PASS, "mongo connected")
    elif m.get("configured"):
        record(FAIL, "mongo connected",
               "configured but NOT connected -- check Atlas network access allows 0.0.0.0/0")
    else:
        record(FAIL, "mongo connected", "not configured; the pipeline will use fixtures")

    # -- 3. groq live and with budget left ---------------------------------
    g = health.get("groq", {})
    rl = health.get("rate_limit") or {}
    remaining = rl.get("remaining_tokens")
    if not g.get("configured"):
        record(FAIL, "groq configured", "every agent will run its deterministic fallback")
    elif remaining is None:
        record(WARN, "groq budget", "no rate-limit reading yet; fire one request to populate it")
    elif remaining < 3000:
        record(FAIL, "groq budget",
               f"only {remaining} tokens/min left -- a full run needs ~1,700. Wait a minute.")
    else:
        record(PASS, "groq budget", f"{remaining} tokens/min remaining, model {g.get('model')}")

    # -- 4. bound on all interfaces so the phone can reach it ---------------
    try:
        ip = socket.gethostbyname(socket.gethostname())
        s = socket.socket()
        s.settimeout(2)
        port = int(args.base.rsplit(":", 1)[-1].rstrip("/"))
        s.connect((ip, port))
        s.close()
        record(PASS, "reachable from the LAN", f"phone should use http://{ip}:{port}")
    except Exception:
        record(WARN, "reachable from the LAN",
               "could not connect via the LAN address; if the phone is in the demo, "
               "restart with --host 0.0.0.0")

    # -- 5. admin auth ------------------------------------------------------
    try:
        tok = call(args.base, "/api/v1/admin/login", "POST",
                   {"username": args.user, "password": args.password})["token"]
        record(PASS, "admin login")
    except Exception as e:
        record(FAIL, "admin login", str(e))
        return summarise()

    # -- 6. auth is actually enforced --------------------------------------
    try:
        call(args.base, "/api/v1/admin/matches")
        record(FAIL, "admin auth enforced", "protected endpoint answered with NO token")
    except urllib.error.HTTPError as e:
        record(PASS if e.code == 401 else WARN, "admin auth enforced", f"no token -> {e.code}")
    except Exception as e:
        record(WARN, "admin auth enforced", str(e))

    # -- 7. org portal ------------------------------------------------------
    try:
        org = call(args.base, "/api/v1/org/login", "POST",
                   {"username": args.org_user, "password": args.org_password})
        if org.get("status") == "ok":
            record(PASS, "org login", f"{org.get('org_name')} ({org.get('group_code')})")
        else:
            record(FAIL, "org login", org.get("error", "unknown"))
    except Exception as e:
        record(FAIL, "org login", str(e))

    # -- 8. the seed is where the demo is ----------------------------------
    seed = call(args.base, "/api/v1/admin/seed", token=tok)
    centre = seed.get("centre")
    if not centre:
        record(FAIL, "fixtures seeded", "no seed centre recorded; POST /api/v1/admin/seed")
    elif args.lat is None or args.lon is None:
        record(WARN, "fixtures near the demo",
               f"seeded at {centre['lat']:.4f}, {centre['lon']:.4f}. "
               "Pass --lat/--lon to check this properly.")
    else:
        d = haversine_km((args.lat, args.lon), (centre["lat"], centre["lon"]))
        ladder = seed.get("radius_ladder_km") or [150]
        if d <= ladder[0]:
            record(PASS, "fixtures near the demo", f"{d:.1f} km away (first rung {ladder[0]} km)")
        elif d <= ladder[-1]:
            record(WARN, "fixtures near the demo",
                   f"{d:.1f} km away -- inside the ladder but past the first rung; "
                   "the query will walk out and ETAs will look long")
        else:
            record(FAIL, "fixtures near the demo",
                   f"{d:.1f} km away, past the {ladder[-1]} km ladder. $geoNear will return "
                   f"NOTHING and the run will use fixtures.\n"
                   f"         Fix: POST /api/v1/admin/seed "
                   f'{{"lat": {args.lat}, "lon": {args.lon}, "label": "venue"}}')

    # -- 9. coordinates are not flipped ------------------------------------
    matches = call(args.base, "/api/v1/admin/matches?limit=1", token=tok)
    record(PASS if isinstance(matches.get("matches"), list) else FAIL,
           "admin endpoints answer")

    # -- 10. a real end-to-end run -----------------------------------------
    if args.no_run:
        record(WARN, "live pipeline run", "skipped (--no-run)")
        return summarise()

    lat = args.lat if args.lat is not None else (centre or {}).get("lat", 23.2599)
    lon = args.lon if args.lon is not None else (centre or {}).get("lon", 77.4126)

    sys.path.insert(0, ".")
    try:
        from app.codec import encode_request
    except Exception as e:
        record(WARN, "live pipeline run", f"run this from backend/ ({e})")
        return summarise()

    payload = encode_request(
        {"situation": "5", "people": "2", "injury": "2", "mobility": "3",
         "urgency": "C", "needs": ["water_kits", "medical_kits"],
         "vulnerability": ["child_under_5"]},
        lat + 0.002, lon + 0.002, "PFLT", int(time.time()) % 900 + 1)

    res = call(args.base, "/api/v1/pact/ingest", "POST",
               {"payload": payload, "transport": "http"})
    trace = res.get("trace_id")
    if res.get("status") != "accepted" or not trace:
        record(FAIL, "live pipeline run", f"ingest rejected: {res}")
        return summarise()

    print("         waiting for the run to finish (autopilot gate ~25 s)...")
    completed = None
    for _ in range(30):
        time.sleep(3)
        tr = call(args.base, f"/api/v1/admin/requests/{trace}/trace", token=tok)
        evs = tr.get("events", [])
        completed = next((e for e in evs if e["type"] == "run.completed"), None)
        if completed:
            break

    if not completed:
        record(FAIL, "live pipeline run", f"{trace} did not complete in 90 s")
        return summarise()

    p = completed["payload"]
    record(PASS if p.get("status") == "committed" else FAIL,
           "live pipeline run", f"{trace} -> {p.get('status')}")

    # The check this whole script exists for.
    if p.get("geo_live"):
        record(PASS, "geo_live", "$geoNear returned real candidates")
    else:
        record(FAIL, "geo_live",
               "the run used FIXTURES, not the database. Reseed near the demo location.")

    agents = p.get("llm_agents") or {}
    live_agents = [k for k, v in agents.items() if v]
    if len(live_agents) == len(agents) and agents:
        record(PASS, "all LLM agents live", ", ".join(live_agents))
    else:
        dead = [k for k, v in agents.items() if not v]
        record(WARN, "all LLM agents live",
               f"fell back to deterministic: {', '.join(dead)} (rate limit?)")

    evs = call(args.base, f"/api/v1/admin/requests/{trace}/trace", token=tok)["events"]
    types = {e["type"] for e in evs}
    for needed, label in [("debate.turn", "advocate debate"),
                          ("options.proposed", "three-option solver"),
                          ("decision.committed", "committed allocation"),
                          ("notify.sent", "dispatch")]:
        record(PASS if needed in types else FAIL, f"never-cut: {label}")

    return summarise()


def summarise() -> int:
    fails = [r for r in results if r[0] == FAIL]
    warns = [r for r in results if r[0] == WARN]
    print("-" * 62)
    if fails:
        print(f"NOT READY -- {len(fails)} failure(s), {len(warns)} warning(s)")
        for _, name, detail in fails:
            print(f"  - {name}: {detail.splitlines()[0] if detail else ''}")
        return 1
    print(f"READY TO RECORD -- {len(warns)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
