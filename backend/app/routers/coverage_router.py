import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
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
    for name in ("coverage_results.json", "coverage_data.json"):
        p = _FRONTEND / name
        if p.exists():
            import json
            return JSONResponse(json.loads(p.read_text(encoding="utf-8")))
    raise HTTPException(status_code=404, detail="Geen coverage JSON gevonden")


@router.get("/timeline")
def coverage_timeline():
    """Timeline van coverage per scandatum (alle coverage_results_DDMMYYYY.json bestanden)."""
    import json
    results_dir = _XR_DIR / "coverage_results"
    entries = []
    for f in sorted(results_dir.glob("coverage_results_????????.json")):
        m = re.search(r"coverage_results_(\d{8})\.json", f.name)
        if not m:
            continue
        key = m.group(1)
        date_str = f"{key[4:]}-{key[2:4]}-{key[:2]}"
        data = json.loads(f.read_text(encoding="utf-8"))
        summary = data.get("summary", {})
        entries.append({
            "date": date_str,
            "key": key,
            "total_coverage_pct": summary.get("total_coverage_pct", 0),
            "built":   summary.get("built", 0),
            "partial": summary.get("partial", 0),
            "missing": summary.get("missing", 0),
        })
    entries.sort(key=lambda e: e["date"])
    return JSONResponse({"entries": entries})


@router.get("/data/{date_key}")
def coverage_data_by_date(date_key: str):
    """Coverage JSON voor een specifieke scandatum, bijv. 18112023.
    Probeert per-type JSON eerst (coverage_results_DDMMYYYY.json),
    valt terug op per-segment JSON (coverage_DDMMYYYY.json).
    """
    import json
    results_dir = _XR_DIR / "coverage_results"
    for filename in (f"coverage_results_{date_key}.json", f"coverage_{date_key}.json"):
        p = results_dir / filename
        if p.exists():
            return JSONResponse(json.loads(p.read_text(encoding="utf-8")))
    raise HTTPException(status_code=404, detail=f"Geen coverage JSON gevonden voor {date_key}")


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
                    headers={"Cache-Control": "no-store"},
                )
    raise HTTPException(status_code=404, detail="Geen coverage PLY gevonden")


@router.get("/pointcloud/{date_key}")
def coverage_pointcloud_by_date(date_key: str):
    """Gekleurde coverage PLY voor een specifieke scandatum, bijv. 18112023."""
    p = _XR_DIR / "coverage_results" / f"coverage_{date_key}.ply"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"coverage_{date_key}.ply niet gevonden")
    return FileResponse(
        path=str(p),
        media_type="application/octet-stream",
        filename=p.name,
        headers={"Cache-Control": "no-store"},
    )
