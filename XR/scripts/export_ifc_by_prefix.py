#!/usr/bin/env python3
"""
List IFC element name prefixes and export elements grouped by prefix to per-prefix GLB files.

Usage:
  # list detected prefixes and counts
  python export_ifc_by_prefix.py /path/to/Bridge.ifc --list

  # export specific prefixes (semicolon-separated)
  python export_ifc_by_prefix.py /path/to/Bridge.ifc --prefixes "KCPD_BTL;KCPT_Ki"

  # export all prefixes (may take a long time)
  python export_ifc_by_prefix.py /path/to/Bridge.ifc --all

The script uses ifcopenshell.geom to tessellate elements and trimesh to export GLB.
It processes one prefix at a time to limit memory usage.
"""
import argparse
from pathlib import Path
import sys

def center_glb(glb_path: Path):
    import trimesh

    scene = trimesh.load(str(glb_path), force='scene')
    centroid = scene.bounding_box.centroid
    if hasattr(scene, 'geometry') and scene.geometry:
        for geom in scene.geometry.values():
            try:
                geom.apply_translation(-centroid)
            except Exception:
                pass
    else:
        try:
            scene.apply_translation(-centroid)
        except Exception:
            pass

    centered_path = glb_path.with_name(glb_path.stem + '_centered.glb')
    scene.export(str(centered_path))
    print(f"Centered {glb_path.name} -> {centered_path.name}")
    return centered_path

def extract_prefix(name: str):
    if not name:
        return None
    s = str(name)
    if '.' in s:
        s = s.split('.', 1)[1]
    s = s.split(':', 1)[0]
    return s.strip()

def list_prefixes(ifc_path: Path):
    import ifcopenshell
    model = ifcopenshell.open(str(ifc_path))
    counts = {}
    for prod in model.by_type('IfcProduct'):
        name = getattr(prod, 'Name', None)
        p = extract_prefix(name) if name else None
        if p:
            counts[p] = counts.get(p, 0) + 1
    return counts

def export_prefix(ifc_path: Path, prefix: str, out_dir: Path, max_items=None):
    import ifcopenshell, ifcopenshell.geom, trimesh, numpy as _np

    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    model = ifcopenshell.open(str(ifc_path))
    meshes = []
    count = 0
    for prod in model.by_type('IfcProduct'):
        name = getattr(prod, 'Name', None)
        p = extract_prefix(name) if name else None
        if prefix.endswith('*'):
            # wildcard: match startswith
            base = prefix[:-1]
            if not p or not p.startswith(base):
                continue
        else:
            if p != prefix:
                continue
        try:
            shape = ifcopenshell.geom.create_shape(settings, prod)
        except Exception:
            continue
        verts = shape.geometry.verts
        faces = shape.geometry.faces
        if not verts or not faces:
            continue
        v = _np.array(verts).reshape((-1,3))
        f = _np.array(faces).reshape((-1,3))
        tm = trimesh.Trimesh(vertices=v, faces=f, process=False)
        meshes.append(tm)
        count += 1
        if max_items and count >= max_items:
            break

    if not meshes:
        print(f"No meshes for prefix {prefix}")
        return False

    scene = trimesh.Scene(meshes)
    out_path = out_dir / f"{prefix.replace(' ', '_')}.glb"
    scene.export(str(out_path))
    print(f"Wrote {out_path} ({len(meshes)} parts)")
    try:
        center_glb(out_path)
    except Exception as e:
        print(f"Centering failed for {out_path.name}: {e}")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ifc', help='Path to IFC file')
    ap.add_argument('--list', action='store_true', help='List prefixes and counts')
    ap.add_argument('--prefixes', help='Semicolon-separated prefixes to export')
    ap.add_argument('--all', action='store_true', help='Export all prefixes')
    ap.add_argument('--out', help='Output directory (default: same folder as IFC)', default=None)
    ap.add_argument('--max', type=int, help='Max items per prefix (useful for testing)', default=None)
    args = ap.parse_args()

    ifc_path = Path(args.ifc)
    if not ifc_path.exists():
        print('IFC not found:', ifc_path)
        return 2
    out_dir = Path(args.out) if args.out else ifc_path.parent.parent / 'GLB_Files'
    out_dir.mkdir(parents=True, exist_ok=True)

    counts = list_prefixes(ifc_path)

    if args.list:
        for k,v in sorted(counts.items(), key=lambda x:-x[1]):
            print(f"{k}: {v}")
        return 0

    targets = []
    if args.all:
        targets = list(counts.keys())
    elif args.prefixes:
        targets = [p.strip() for p in args.prefixes.split(';') if p.strip()]
    else:
        print('No action specified. Use --list, --prefixes or --all')
        return 2

    for t in targets:
        if t not in counts:
            print(f"Warning: prefix not found: {t}")
            continue
        print('Exporting prefix', t)
        ok = export_prefix(ifc_path, t, out_dir, max_items=args.max)
        if not ok:
            print('Export failed for', t)

    return 0

if __name__ == '__main__':
    sys.exit(main())
