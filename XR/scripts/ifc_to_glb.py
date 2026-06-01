#!/usr/bin/env python3
"""Convert an IFC file to GLB (binary glTF).

Workflow:
- Prefer using the `ifcconvert` CLI (IfcOpenShell) to produce an OBJ, then convert OBJ -> GLB with trimesh.
- If `ifcconvert` is not available, attempt a Python-only path using ifcopenshell + ifcopenshell.geom.

Usage:
    python scripts/ifc_to_glb.py /path/to/XL8.ifc [output.glb]

The script writes `output.glb` (or same basename with .glb) on success.
"""
import os
import sys
import subprocess
from pathlib import Path

def run_cmd(cmd):
    print("Running:", " ".join(cmd))
    try:
        rc = subprocess.run(cmd, check=False)
        return rc.returncode == 0
    except FileNotFoundError:
        # Command not found (e.g., ifcconvert not installed)
        print(f"Command not found: {cmd[0]}")
        return False

def convert_with_ifcconvert(ifc_path: Path, obj_path: Path) -> bool:
    # Try to call ifcconvert (provided by IfcOpenShell)
    return run_cmd(["ifcconvert", str(ifc_path), str(obj_path)])

def obj_to_glb(obj_path: Path, glb_path: Path) -> bool:
    try:
        import trimesh
    except Exception as e:
        print("trimesh not available:", e)
        return False
    print(f"Loading OBJ {obj_path} (this may take a while)...")
    mesh = trimesh.load(str(obj_path), force='mesh', skip_materials=False)
    if mesh is None:
        print("Failed to load OBJ as mesh")
        return False
    print(f"Exporting to {glb_path}...")
    mesh.export(str(glb_path), file_type='glb')
    return glb_path.exists()

def try_python_tessellate(ifc_path: Path, glb_path: Path) -> bool:
    try:
        import ifcopenshell
        import ifcopenshell.geom
        import trimesh
    except Exception as e:
        print("Python tessellation prerequisites missing:", e)
        return False

    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    model = ifcopenshell.open(str(ifc_path))
    meshes = []
    for prod in model.by_type('IfcProduct'):
        try:
            shape = ifcopenshell.geom.create_shape(settings, prod)
        except Exception:
            continue
        verts = shape.geometry.verts
        faces = shape.geometry.faces
        # verts is flat list [x,y,z,x,y,z,...]
        import numpy as _np
        v = _np.array(verts).reshape((-1,3))
        f = _np.array(faces).reshape((-1,3))
        tm = trimesh.Trimesh(vertices=v, faces=f, process=False)
        meshes.append(tm)

    if not meshes:
        print("No meshes created from IFC products")
        return False

    scene = trimesh.Scene(meshes)
    scene.export(str(glb_path))
    return glb_path.exists()

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/ifc_to_glb.py /path/to/XL8.ifc [out.glb]")
        sys.exit(2)
    ifc_path = Path(sys.argv[1])
    if not ifc_path.exists():
        print("IFC not found:", ifc_path)
        sys.exit(1)
    out = Path(sys.argv[2]) if len(sys.argv) >= 3 else ifc_path.with_suffix('.glb')

    tmp_obj = ifc_path.with_suffix('.obj')

    # 1) Try ifcconvert -> OBJ
    if convert_with_ifcconvert(ifc_path, tmp_obj):
        print("Converted IFC -> OBJ using ifcconvert")
        if obj_to_glb(tmp_obj, out):
            print("Successfully wrote", out)
            sys.exit(0)
        else:
            print("OBJ -> GLB conversion failed")

    # 2) Try python tessellation path
    print("Attempting Python tessellation path (ifcopenshell.geom + trimesh)")
    if try_python_tessellate(ifc_path, out):
        print("Successfully wrote", out)
        sys.exit(0)

    print("All conversion attempts failed. Ensure IfcOpenShell's ifcconvert is installed or that ifcopenshell.geom is available.")
    sys.exit(3)

if __name__ == '__main__':
    main()
