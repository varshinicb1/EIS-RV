"""
Mesh Utilities
===============
Convert geometry to triangle meshes for 3D preview rendering.
Supports both CadQuery shapes and native MeshSolid objects.
"""

import math
import numpy as np
from typing import Tuple, Optional, List, Dict

try:
    import cadquery as cq
    HAS_CADQUERY = True
except ImportError:
    HAS_CADQUERY = False


def shape_to_mesh(shape_or_mesh, tolerance: float = 0.05
                  ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert a shape to triangle mesh arrays.

    Supports:
        - CadQuery Shape objects
        - MeshSolid objects (native kernel)

    Returns:
        (vertices, faces, normals)
    """
    from ..core.geometry_engine import MeshSolid

    if isinstance(shape_or_mesh, MeshSolid):
        verts = shape_or_mesh.vertices.astype(np.float32)
        faces = shape_or_mesh.faces.astype(np.int32)
        normals = compute_vertex_normals(verts, faces)
        return verts, faces, normals

    if HAS_CADQUERY and hasattr(shape_or_mesh, 'tessellate'):
        try:
            verts_cq, tris_cq = shape_or_mesh.tessellate(tolerance)
            if len(verts_cq) == 0:
                return _create_placeholder_mesh()

            vertices = np.array(
                [(v.x, v.y, v.z) for v in verts_cq], dtype=np.float32
            )
            faces = np.array(tris_cq, dtype=np.int32)
            normals = compute_vertex_normals(vertices, faces)
            return vertices, faces, normals
        except Exception as e:
            print(f"CadQuery tessellation error: {e}")

    return _create_placeholder_mesh()


def workplane_to_mesh(wp, tolerance: float = 0.05
                      ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert a CadQuery Workplane or MeshSolid to triangle mesh.
    """
    from ..core.geometry_engine import MeshSolid

    if isinstance(wp, MeshSolid):
        return shape_to_mesh(wp, tolerance)

    if HAS_CADQUERY and hasattr(wp, 'val'):
        try:
            shape = wp.val()
            return shape_to_mesh(shape, tolerance)
        except Exception:
            try:
                all_verts = []
                all_faces = []
                offset = 0
                for solid in wp.solids().vals():
                    v, f, _ = shape_to_mesh(solid, tolerance)
                    all_faces.append(f + offset)
                    all_verts.append(v)
                    offset += len(v)
                if all_verts:
                    vertices = np.vstack(all_verts)
                    faces = np.vstack(all_faces)
                    normals = compute_vertex_normals(vertices, faces)
                    return vertices, faces, normals
            except Exception:
                pass

    return _create_placeholder_mesh()


def compute_vertex_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Compute smooth vertex normals from face normals."""
    normals = np.zeros_like(vertices, dtype=np.float32)

    if len(faces) == 0:
        return normals

    # Ensure face indices are within bounds
    max_idx = len(vertices) - 1
    valid_mask = np.all(faces <= max_idx, axis=1) & np.all(faces >= 0, axis=1)
    valid_faces = faces[valid_mask]

    if len(valid_faces) == 0:
        return normals

    v0 = vertices[valid_faces[:, 0]]
    v1 = vertices[valid_faces[:, 1]]
    v2 = vertices[valid_faces[:, 2]]

    edge1 = v1 - v0
    edge2 = v2 - v0
    face_normals = np.cross(edge1, edge2)

    for i in range(3):
        np.add.at(normals, valid_faces[:, i], face_normals)

    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths[lengths < 1e-10] = 1.0
    normals /= lengths

    return normals


def compute_mesh_bounds(vertices: np.ndarray) -> dict:
    """Compute bounding box and center of a mesh."""
    if len(vertices) == 0:
        return {"min": [0, 0, 0], "max": [1, 1, 1],
                "center": [0.5, 0.5, 0.5], "size": 1.0}

    vmin = vertices.min(axis=0)
    vmax = vertices.max(axis=0)
    center = (vmin + vmax) / 2.0
    size = float(np.linalg.norm(vmax - vmin))

    return {
        "min": vmin.tolist(), "max": vmax.tolist(),
        "center": center.tolist(), "size": size
    }


def _create_placeholder_mesh() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create a simple box mesh as placeholder."""
    s = 5.0
    h = 1.0

    vertices = np.array([
        [-s, -s, 0], [s, -s, 0], [s, s, 0], [-s, s, 0],
        [-s, -s, h], [s, -s, h], [s, s, h], [-s, s, h],
    ], dtype=np.float32)

    faces = np.array([
        [0, 1, 2], [0, 2, 3],
        [4, 6, 5], [4, 7, 6],
        [0, 5, 1], [0, 4, 5],
        [2, 7, 3], [2, 6, 7],
        [0, 3, 7], [0, 7, 4],
        [1, 5, 6], [1, 6, 2],
    ], dtype=np.int32)

    normals = compute_vertex_normals(vertices, faces)
    return vertices, faces, normals
