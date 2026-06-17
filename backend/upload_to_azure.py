"""
Upload alle PLY, IFC en GLB bestanden naar Azure Blob Storage (3dmodels container).

Gebruik:
    cd backend
    python upload_to_azure.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from app.db.azure_storage import upload_file_to_blob, MODELS_CONTAINER

ROOT = Path(__file__).parent.parent
XR   = ROOT / "XR" / "IFC-TO-Cloud"
FE   = ROOT / "Frontend"

# (lokaal pad, blob pad in 3dmodels container)
FILES = []

# Pointclouds per datum
for p in sorted((XR / "Allpointclouds").glob("pointcloud_*.ply")):
    FILES.append((p, f"pointclouds/{p.name}"))

# Coverage PLYs per datum
for p in sorted((XR / "coverage_results").glob("coverage_*.ply")):
    FILES.append((p, f"coverage/{p.name}"))

# Losse coverage PLYs
for name in ("coverage_colored.ply", "coverage_result.ply"):
    p = XR / name
    if p.exists():
        FILES.append((p, f"coverage/{name}"))

# IFC
ifc = XR / "brug.ifc"
if ifc.exists():
    FILES.append((ifc, "ifc/brug.ifc"))

# GLB (BIM model)
glb = FE / "KCPT_Ki_centered.glb"
if glb.exists():
    FILES.append((glb, "glb/KCPT_Ki_centered.glb"))

print(f"Uploading {len(FILES)} bestanden naar Azure '{MODELS_CONTAINER}' container...\n")

errors = []
for local_path, blob_path in FILES:
    ext = local_path.suffix.lower()
    ct_map = {".ply": "application/octet-stream", ".ifc": "application/octet-stream", ".glb": "model/gltf-binary"}
    content_type = ct_map.get(ext, "application/octet-stream")
    try:
        url = upload_file_to_blob(MODELS_CONTAINER, blob_path, str(local_path), content_type)
        size_mb = local_path.stat().st_size / 1024 / 1024
        print(f"  OK  {blob_path} ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"  ERR {blob_path}: {e}")
        errors.append(blob_path)

print(f"\nKlaar — {len(FILES) - len(errors)}/{len(FILES)} geüpload.")
if errors:
    print("Mislukt:", errors)
    sys.exit(1)
