#!/usr/bin/env python3
"""
IFC → Point Cloud (voor Open3D + ICP testing)
"""

import argparse
import time
import traceback
import sys

import numpy as np
import trimesh
import ifcopenshell
import ifcopenshell.geom


def build_mesh(ifc_path):
    start = time.time()
    print(f"Opening IFC: {ifc_path}")
    try:
        model = ifcopenshell.open(ifc_path)

        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        iterator = ifcopenshell.geom.iterator(settings, model)

        all_verts = []
        all_faces = []
        offset = 0
        count = 0

        if iterator.initialize():
            print("Iterator initialized, starting element loop")
            while True:
                shape = iterator.get()
                geo = shape.geometry

                verts = np.array(geo.verts, dtype=np.float64).reshape(-1, 3)
                faces = np.array(geo.faces, dtype=np.int64).reshape(-1, 3)

                if len(verts) > 0 and len(faces) > 0:
                    all_verts.append(verts)
                    all_faces.append(faces + offset)
                    offset += len(verts)
                    count += 1

                    if count % 50 == 0:
                        print(f"Processed {count} elements, accumulated vertices: {offset}")

                if not iterator.next():
                    break
        else:
            print("Iterator failed to initialize or no geometry available")

        print(f"Elements processed: {count}")

        if len(all_verts) == 0 or len(all_faces) == 0:
            print("No geometry extracted from IFC. Returning empty mesh.")
            vertices = np.zeros((0, 3), dtype=np.float64)
            faces = np.zeros((0, 3), dtype=np.int64)
        else:
            vertices = np.vstack(all_verts)
            faces = np.vstack(all_faces)

        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        duration = time.time() - start
        print(f"build_mesh finished in {duration:.2f}s — vertices={len(mesh.vertices)} faces={len(mesh.faces)}")
        try:
            bbox = mesh.bounds
            span = bbox[1] - bbox[0]
            longest_axis = int(np.argmax(span))
            print(f"Mesh bounds min={bbox[0].tolist()} max={bbox[1].tolist()} span={span.tolist()} longest_axis={longest_axis}")
        except Exception:
            pass
        return mesh
    except Exception:
        print("Exception in build_mesh:")
        traceback.print_exc()
        raise


def sample_pointcloud(mesh, n_points=500000):
    print(f"Sampling pointcloud: requested {n_points} points")
    try:
        nv = len(mesh.vertices) if mesh is not None else 0
        nf = len(mesh.faces) if mesh is not None else 0
        print(f"Mesh stats before sampling: vertices={nv} faces={nf}")
        try:
            bbox = mesh.bounds
            span = bbox[1] - bbox[0]
            longest_extent = float(np.max(span))
            if longest_extent > 0.0:
                density = float(n_points) / longest_extent
                print(f"Sampling density (points per meter along longest axis): {density:.2f}")
        except Exception:
            pass
        start = time.time()
        points, face_idx = trimesh.sample.sample_surface(mesh, n_points)
        normals = mesh.face_normals[face_idx]
        duration = time.time() - start
        print(f"sample_pointcloud finished in {duration:.2f}s — sampled points={len(points)}")
        return points, normals
    except Exception:
        print("Exception in sample_pointcloud:")
        traceback.print_exc()
        raise


def scale_mesh_to_length(mesh, target_length):
    if mesh is None or target_length is None or target_length <= 0:
        return mesh, 1.0

    bbox = mesh.bounds
    span = bbox[1] - bbox[0]
    longest_extent = float(np.max(span))
    if longest_extent <= 0.0:
        return mesh, 1.0

    scale = float(target_length) / longest_extent
    center = bbox.mean(axis=0)
    scaled_vertices = (mesh.vertices - center) * scale + center
    scaled_mesh = trimesh.Trimesh(vertices=scaled_vertices, faces=mesh.faces, process=False)
    return scaled_mesh, scale


def export_ply(points, normals, output):
    import open3d as o3d
    try:
        print(f"Exporting point cloud to: {output}")
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.normals = o3d.utility.Vector3dVector(normals)

        o3d.io.write_point_cloud(output, pcd)
        print(f"Saved: {output}")
    except Exception:
        print("Exception in export_ply:")
        traceback.print_exc()
        raise


def view_pointcloud(path):
    import open3d as o3d
    print(f"Loading point cloud for viewer: {path}")
    pcd = o3d.io.read_point_cloud(path)
    pts = np.asarray(pcd.points)
    print(f"Viewer loaded: points={len(pcd.points)}")
    if len(pts) > 0:
        mins = pts.min(axis=0)
        maxs = pts.max(axis=0)
        span = maxs - mins
        print(f"Point cloud extent XYZ: {span.tolist()}")
        print(f"Longest axis: {float(np.max(span)):.3f}m")
    o3d.visualization.draw_geometries([pcd], window_name="IFC Point Cloud")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ifc", help="Path to IFC file")
    parser.add_argument("-o", "--output", default="ifc_cloud.ply")
    parser.add_argument("-n", "--n_points", type=int, default=500000)
    parser.add_argument("--expected-length", type=float, default=494.0, help="Expected bridge length for scale checking")
    parser.add_argument("--scale-to-expected", action="store_true", help="Scale the mesh to the expected bridge length before sampling")
    parser.add_argument("--no-view", action="store_true", help="Do not open the exported point cloud in a viewer")
    args = parser.parse_args()
    print(f"Arguments: ifc={args.ifc} output={args.output} n_points={args.n_points} expected_length={args.expected_length} no_view={getattr(args, 'no_view', False)}")
    try:
        t0 = time.time()
        mesh = build_mesh(args.ifc)
        try:
            bbox = mesh.bounds
            span = bbox[1] - bbox[0]
            longest = float(np.max(span))
            if args.expected_length and args.expected_length > 0:
                ratio = longest / args.expected_length
                print(f"Scale check: longest_extent={longest:.3f}m expected_length={args.expected_length:.3f}m ratio={ratio:.4f}")
                print(f"Scale check: bridge_length_error={abs(longest - args.expected_length):.3f}m")
        except Exception:
            pass

        if args.scale_to_expected:
            original_bbox = mesh.bounds.copy()
            mesh, scale = scale_mesh_to_length(mesh, args.expected_length)
            print(f"Applied mesh scale factor: {scale:.6f} to match expected length {args.expected_length:.3f}m")
            # Sla transformatie-info op zodat coverage_per_type.py dezelfde schaal kan toepassen
            import json, pathlib
            transform_path = pathlib.Path(args.output).with_suffix(".transform.json")
            transform_info = {
                "scale": float(scale),
                "center": original_bbox.mean(axis=0).tolist(),
                "original_bbox_min": original_bbox[0].tolist(),
                "original_bbox_max": original_bbox[1].tolist(),
                "target_length": float(args.expected_length),
                "ifc_path": str(args.ifc)
            }
            transform_path.write_text(json.dumps(transform_info, indent=2))
            print(f"Transform info saved: {transform_path}")

        points, normals = sample_pointcloud(mesh, args.n_points)
        export_ply(points, normals, args.output)
        # Open viewer by default unless --no-view was passed
        if not getattr(args, "no_view", False):
            try:
                view_pointcloud(args.output)
            except Exception:
                print("Viewer failed to open (continuing).")
        total = time.time() - t0
        print(f"Done. Total runtime: {total:.2f}s")
    except Exception:
        print("Unhandled exception in main:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()