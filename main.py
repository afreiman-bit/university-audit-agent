import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator.agent import sweep_url, sweep_url_list

app = FastAPI(
    title="University Web Audit Agent",
    description="Multi-agent AEO scoring and cross-page coherence for university program pages.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = {}

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=open("static/index.html").read())


@app.post("/sweep")
async def start_sweep(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    urls = body.get("urls", [])
    tenant = body.get("tenant", "demo")
    deliver = body.get("deliver_to_contoro", False)

    if not urls:
        return JSONResponse({"error": "No URLs provided"}, status_code=400)

    if len(urls) == 1:
        result = await sweep_url(
            url=urls[0]["url"],
            tenant=tenant,
            school=urls[0].get("school"),
            department=urls[0].get("department"),
            page_type=urls[0].get("page_type", "program"),
            deliver=deliver,
        )
        return JSONResponse(result)

    import uuid
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "total": len(urls), "completed": 0, "results": []}

    async def run_sweep():
        results = await sweep_url_list(urls=urls, tenant=tenant, deliver=deliver)
        jobs[job_id] = {
            "status": "complete",
            "total": len(urls),
            "completed": len(results),
            "results": results,
        }

    background_tasks.add_task(run_sweep)
    return JSONResponse({"job_id": job_id, "status": "running", "total": len(urls)})


@app.get("/sweep/{job_id}")
async def get_sweep_status(job_id: str):
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse(jobs[job_id])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/ground-truth")
async def ground_truth():
    gt_path = Path("config/ground_truth.json")
    if gt_path.exists():
        return JSONResponse(json.loads(gt_path.read_text()))
    return JSONResponse({"error": "Ground truth file not found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
