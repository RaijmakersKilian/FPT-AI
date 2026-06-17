import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers.video_router import router as video_router
from app.routers.processing_router import router as processing_router
from app.routers.report_router import router as report_router
from app.routers.element_type_router import router as element_type_router
from app.routers.detected_element_router import router as detected_element_router
from app.routers.coverage_router import router as coverage_router

_ROOT        = Path(__file__).parent.parent.parent
FRONTEND_DIR = _ROOT / "Frontend"
_XR_DIR      = _ROOT / "XR" / "IFC-TO-Cloud"


async def _run_coverage_analysis() -> None:
    ifc_in   = _XR_DIR / "ifc_cloud.ply"
    scan_in  = _XR_DIR / "mast3r_filtered.ply"
    out_ply  = FRONTEND_DIR / "coverage_result.ply"
    out_json = FRONTEND_DIR / "coverage_data.json"

    if not ifc_in.exists() or not scan_in.exists():
        print("[startup] Coverage-inputbestanden niet gevonden, analyse overgeslagen.")
        return

    # Skip if output files are newer than both inputs
    if out_ply.exists() and out_json.exists():
        latest_in  = max(ifc_in.stat().st_mtime, scan_in.stat().st_mtime)
        oldest_out = min(out_ply.stat().st_mtime, out_json.stat().st_mtime)
        if oldest_out >= latest_in:
            print("[startup] Coverage-resultaten zijn actueel, analyse overgeslagen.")
            return

    print("[startup] Coverage-analyse gestart op achtergrond...")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "coverage_analysis.py",
        "--ifc",         "ifc_cloud.ply",
        "--mast3r",      "mast3r_filtered.ply",
        "--export-ply",  str(out_ply),
        "--export-json", str(out_json),
        cwd=str(_XR_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode == 0:
        print("[startup] Coverage-analyse klaar — resultaten geladen.")
    else:
        print(f"[startup] Coverage-analyse mislukt (code {proc.returncode}): "
              f"{stderr.decode(errors='replace')[:300]}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_run_coverage_analysis())
    yield


app = FastAPI(
    title="FPT AI Construction Progress API",
    description="Backend API for UAV video processing and construction progress monitoring",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def serve_dashboard():
    return FileResponse(str(FRONTEND_DIR / "Dashboard.html"))


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(video_router,           prefix="/videos",            tags=["Videos"])
app.include_router(processing_router,      prefix="/processing-runs",   tags=["Processing Runs"])
app.include_router(report_router,          prefix="/reports",           tags=["Reports"])
app.include_router(element_type_router,    prefix="/element-types",     tags=["Element Types"])
app.include_router(detected_element_router,prefix="/detected-elements", tags=["Detected Elements"])
app.include_router(coverage_router,        prefix="/api/coverage",      tags=["Coverage"])

# Serve the Frontend — mounted last so API routes take priority
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
