from uuid import uuid4

from app.schemas.processing_schema import ProcessingRunCreate


processing_runs_db = []


def start_processing(payload: ProcessingRunCreate):
    run = {
        "run_id": str(uuid4()),
        "video_id": payload.video_id,
        "status": "pending",
        "message": "Processing run created successfully"
    }

    processing_runs_db.append({
        **run,
        "progress": 0,
        "current_stage": "waiting"
    })

    return run


def get_processing_status(run_id: str):
    for run in processing_runs_db:
        if run["run_id"] == run_id:
            return {
                "run_id": run["run_id"],
                "status": run["status"],
                "progress": run["progress"],
                "current_stage": run["current_stage"]
            }

    return None