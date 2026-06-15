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

FRONTEND_DIR = Path(__file__).parent.parent.parent / "Frontend"

app = FastAPI(
    title="FPT AI Construction Progress API",
    description="Backend API for UAV video processing and construction progress monitoring",
    version="0.1.0",
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
