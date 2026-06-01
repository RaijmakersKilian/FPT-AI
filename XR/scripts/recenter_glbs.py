#!/usr/bin/env python3
"""Re-center GLB files by subtracting scene centroid and write *_centered.glb files."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] / 'GLB_Files'
if not root.exists():
    print('GLB_Files folder not found at', root)
    sys.exit(1)

import trimesh

for p in sorted(root.glob('*.glb')):
    if p.stem.endswith('_centered'):
        continue
    out = p.with_name(p.stem + '_centered.glb')
    try:
        scene = trimesh.load(str(p), force='scene')
        centroid = scene.bounding_box.centroid
        print(f"Re-centering {p.name} by {centroid} -> {out.name}")
        # translate each geometry
        if hasattr(scene, 'geometry') and scene.geometry:
            for name, geom in scene.geometry.items():
                try:
                    geom.apply_translation(-centroid)
                except Exception:
                    pass
        else:
            # single mesh
            try:
                scene.apply_translation(-centroid)
            except Exception:
                pass
        scene.export(str(out))
    except Exception as e:
        print(f"Failed {p.name}: {e}")
