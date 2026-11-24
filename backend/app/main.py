"""Runnable scaffold: deliberately does not implement simulation business."""
from pathlib import Path
import json
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "data" / "fixtures"
app = FastAPI(title="校园共享单车仿真 · 开发骨架", version="0.1.0")
app.mount("/assets/fixtures", StaticFiles(directory=FIXTURES), name="fixture-assets")


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "stage": "scaffold"}


@app.get("/api/v1/runtime")
def runtime():
    return {"mode": "idle", "run_id": None, "batch_id": None}


@app.get("/api/v1/map")
def map_info():
    meta = json.loads((FIXTURES / "metadata.json").read_text(encoding="utf-8"))
    return {k: meta[k] for k in ["profile", "width", "height", "network_version", "synthetic", "snap_tolerance_px"]} | {
        "image_url": "/assets/fixtures/" + meta["image_file"]}


@app.get("/api/v1/roads")
def roads():
    return json.loads((FIXTURES / "road_network.json").read_text(encoding="utf-8"))


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
def not_implemented(path: str, request: Request):
    return JSONResponse(status_code=501, content={"code": "NOT_IMPLEMENTED",
        "message": "该业务接口尚未实现", "details": {"path": path, "method": request.method}})
