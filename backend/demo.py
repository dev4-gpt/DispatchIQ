"""Exercise the running API. Default is preview-only; --approve explicitly commits synthetic demo work."""

import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .scenario import demo_emergency


def call(url: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--approve", action="store_true", help="Explicitly approve the synthetic emergency proposal")
    parser.add_argument("--reset", action="store_true", help="Reset the synthetic scenario before previewing")
    parser.add_argument("--impossible", action="store_true", help="Use a deadline that no technician can meet")
    args = parser.parse_args()
    root = args.url.rstrip("/")
    snapshot = call(root + "/api/scenario")

    def metadata(s):
        return {"scenario_id": s["scenario_id"], "scenario_epoch": s["scenario_epoch"], "base_revision": s["revision"]}

    if args.reset:
        snapshot = call(root + "/api/reset", "POST", metadata(snapshot))
    ids = {j["id"] for j in snapshot["jobs"]}
    index = 1
    while f"E{index:02}" in ids:
        index += 1
    event = demo_emergency(impossible=args.impossible, job_id=f"E{index:02}").model_dump(mode="json")
    proposal = call(root + "/api/events/preview", "POST", {**metadata(snapshot), "event": event, "strategy": "stable_insertion"})
    assert call(root + "/api/scenario") == snapshot, "Preview unexpectedly mutated committed state"
    print(json.dumps({"proposal_id": proposal["proposal_id"], "status": proposal["status"],
                      "validation": proposal["validation"], "changes": proposal["changes"],
                      "comparison": proposal["comparison"], "runtime_ms": proposal["runtime_ms"],
                      "search": proposal["search"], "explanation": proposal["explanation"]}, indent=2))
    if args.approve and proposal["status"] == "ready":
        committed = call(root + "/api/events/commit", "POST", {**metadata(snapshot), "proposal_id": proposal["proposal_id"]})
        print(f"Approved synthetic demo proposal; revision {committed['revision']}.")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as exc:
        print(exc.read().decode())
        raise SystemExit(1) from exc
