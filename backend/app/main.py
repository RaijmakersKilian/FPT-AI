from fastapi import FastAPI

from app.routers.video_router import router as video_router
from app.routers.processing_router import router as processing_router
from app.routers.report_router import router as report_router
from app.routers.element_type_router import router as element_type_router

app = FastAPI(
    title="FPT AI Construction Progress API",
    description="Backend API for UAV video processing and construction progress monitoring",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "message": "FPT AI backend is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


app.include_router(video_router, prefix="/videos", tags=["Videos"])
app.include_router(processing_router, prefix="/processing-runs", tags=["Processing Runs"])
app.include_router(report_router, prefix="/reports", tags=["Reports"])
app.include_router(element_type_router, prefix="/element-types", tags=["Element Types"])