from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()

_ROOT     = Path(__file__).parent.parent.parent.parent   # project root
_FRONTEND = _ROOT / "Frontend"
_XR_DIR   = _ROOT / "XR" / "IFC-TO-Cloud"


def _find(filename: str) -> Path:
    """Look in Frontend first, then XR/IFC-TO-Cloud."""
    for d in (_FRONTEND, _XR_DIR):
        p = d / filename
        if p.exists():
            return p
    raise HTTPException(status_code=404, detail=f"{filename} niet gevonden")


@router.get("/data")
def coverage_data():
    """Coverage JSON (per-type of per-segment)."""
    # coverage_results.json = per-type with proper category names (preferred),
    # coverage_data.json = per-segment fallback
    for name in ("coverage_results.json", "coverage_data.json"):
        p = _FRONTEND / name
        if p.exists():
            import json
            return JSONResponse(json.loads(p.read_text(encoding="utf-8")))
    raise HTTPException(status_code=404, detail="Geen coverage JSON gevonden")


@router.get("/pointcloud")
def coverage_pointcloud():
    """Gekleurde coverage PLY voor Three.js PLYLoader."""
    # coverage_analysis.py writes coverage_result.ply (preferred),
    # coverage_per_type.py writes coverage_colored.ply (fallback)
    for name in ("coverage_result.ply", "coverage_colored.ply"):
        for d in (_FRONTEND, _XR_DIR):
            p = d / name
            if p.exists():
                return FileResponse(
                    path=str(p),
                    media_type="application/octet-stream",
                    filename=name,
                )
    raise HTTPException(status_code=404, detail="Geen coverage PLY gevonden")
