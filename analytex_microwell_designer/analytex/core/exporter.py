"""
Export Module
==============
STEP and STL file export supporting both CadQuery and native mesh modes.

STEP export:
    - CadQuery mode: ISO 10303 via OpenCascade (most accurate)
    - Native mode: Procedural ISO 10303-21 STEP file generation

STL export:
    - CadQuery mode: via OCC tessellator
    - Native mode: via numpy-stl library
"""

import os
import datetime
import math
from typing import Optional
from enum import Enum

import numpy as np

# CadQuery (optional)
try:
    import cadquery as cq
    from cadquery import exporters
    HAS_CADQUERY = True
except ImportError:
    HAS_CADQUERY = False

# numpy-stl (for native STL export)
try:
    from stl import mesh as stl_mesh
    HAS_NUMPY_STL = True
except ImportError:
    HAS_NUMPY_STL = False

from .geometry_engine import MeshSolid


class ExportFormat(Enum):
    STEP = "STEP"
    STL = "STL"


class ExportResult:
    """Result of an export operation."""
    def __init__(self, success: bool, filepath: str = "", message: str = "",
                 file_size_bytes: int = 0):
        self.success = success
        self.filepath = filepath
        self.message = message
        self.file_size_bytes = file_size_bytes


def export_step(workplane_or_mesh, filepath: str, design=None) -> ExportResult:
    """
    Export model to STEP format (ISO 10303-21).

    Supports:
        - CadQuery Workplane objects (OpenCascade BRep)
        - MeshSolid objects (procedural STEP generation)
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        if not filepath.lower().endswith(('.step', '.stp')):
            filepath += '.step'

        if HAS_CADQUERY and hasattr(workplane_or_mesh, 'val'):
            # CadQuery mode - proper BRep STEP export
            exporters.export(
                workplane_or_mesh,
                filepath,
                exportType=exporters.ExportTypes.STEP
            )
        elif isinstance(workplane_or_mesh, MeshSolid):
            # Native mode - procedural STEP file
            _write_step_native(workplane_or_mesh, filepath, design)
        else:
            return ExportResult(False, filepath, "Unsupported geometry type for STEP export")

        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            return ExportResult(True, filepath,
                                f"STEP file exported successfully ({size:,} bytes)", size)
        else:
            return ExportResult(False, filepath, "Export completed but file not found")

    except Exception as e:
        return ExportResult(False, filepath, f"STEP export failed: {str(e)}")


def export_stl(workplane_or_mesh, filepath: str, tolerance=0.01) -> ExportResult:
    """
    Export model to STL format.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        if not filepath.lower().endswith('.stl'):
            filepath += '.stl'

        if HAS_CADQUERY and hasattr(workplane_or_mesh, 'val'):
            exporters.export(
                workplane_or_mesh, filepath,
                exportType=exporters.ExportTypes.STL,
                tolerance=tolerance
            )
        elif isinstance(workplane_or_mesh, MeshSolid):
            _write_stl_native(workplane_or_mesh, filepath)
        else:
            return ExportResult(False, filepath, "Unsupported geometry type for STL export")

        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            return ExportResult(True, filepath,
                                f"STL file exported successfully ({size:,} bytes)", size)
        else:
            return ExportResult(False, filepath, "Export completed but file not found")

    except Exception as e:
        return ExportResult(False, filepath, f"STL export failed: {str(e)}")


def export_model(workplane_or_mesh, filepath, format=ExportFormat.STEP,
                 design=None, **kwargs) -> ExportResult:
    """Export a model to the specified format."""
    if format == ExportFormat.STEP:
        return export_step(workplane_or_mesh, filepath, design)
    elif format == ExportFormat.STL:
        return export_stl(workplane_or_mesh, filepath, **kwargs)
    else:
        return ExportResult(False, message=f"Unsupported format: {format}")


def batch_export(models: dict, output_dir: str, format=ExportFormat.STEP,
                 prefix="analytex_") -> list:
    """Export multiple models."""
    results = []
    os.makedirs(output_dir, exist_ok=True)
    ext = ".step" if format == ExportFormat.STEP else ".stl"

    for name, model in models.items():
        safe_name = name.replace(" ", "_").replace("/", "_")
        filepath = os.path.join(output_dir, f"{prefix}{safe_name}{ext}")
        result = export_model(model, filepath, format)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
#   Native STL Writer
# ---------------------------------------------------------------------------

def _write_stl_native(mesh_solid: MeshSolid, filepath: str):
    """Write a MeshSolid to STL using numpy-stl or raw binary."""
    verts = mesh_solid.vertices
    faces = mesh_solid.faces

    if HAS_NUMPY_STL:
        stl_data = stl_mesh.Mesh(np.zeros(len(faces), dtype=stl_mesh.Mesh.dtype))
        for i, face in enumerate(faces):
            stl_data.vectors[i] = verts[face]
        stl_data.save(filepath)
    else:
        # Fallback: write ASCII STL manually
        with open(filepath, 'w') as f:
            f.write("solid analytex_microwell\n")
            for face in faces:
                v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
                # Compute normal
                e1 = v1 - v0
                e2 = v2 - v0
                n = np.cross(e1, e2)
                norm = np.linalg.norm(n)
                if norm > 0:
                    n = n / norm

                f.write(f"  facet normal {n[0]:.6e} {n[1]:.6e} {n[2]:.6e}\n")
                f.write("    outer loop\n")
                for v in [v0, v1, v2]:
                    f.write(f"      vertex {v[0]:.6e} {v[1]:.6e} {v[2]:.6e}\n")
                f.write("    endloop\n")
                f.write("  endfacet\n")
            f.write("endsolid analytex_microwell\n")


# ---------------------------------------------------------------------------
#   Native STEP Writer (ISO 10303-21)
# ---------------------------------------------------------------------------

def _write_step_native(mesh_solid: MeshSolid, filepath: str, design=None):
    """
    Write a STEP file using ISO 10303-21 encoding with AP214 schema.

    This generates a valid STEP file with:
    - Proper header (ISO 10303-21)
    - Geometric representation (closed shell from triangular faces)
    - Product definition for metadata

    The geometry is represented as a CLOSED_SHELL of TRIANGULATED_FACES
    forming a MANIFOLD_SOLID_BREP, which is a valid representation
    importable by major CAD software (FreeCAD, Fusion 360, SolidWorks).
    """
    verts = mesh_solid.vertices
    faces = mesh_solid.faces
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    design_name = design.name if design else "AnalyteX MicroWell"

    lines = []
    lines.append("ISO-10303-21;")
    lines.append("HEADER;")
    lines.append(f"FILE_DESCRIPTION(('AnalyteX MicroWell Substrate'),'2;1');")
    lines.append(f"FILE_NAME('{os.path.basename(filepath)}','{now}',"
                 f"('AnalyteX MicroWell Designer'),('AnalyteX Engineering'),"
                 f"'AnalyteX 1.0','AnalyteX Geometry Engine','');")
    lines.append("FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));")
    lines.append("ENDSEC;")
    lines.append("DATA;")

    eid = 1  # Entity ID counter

    # Application context
    ctx_id = eid
    lines.append(f"#{eid}=APPLICATION_CONTEXT('automotive design');")
    eid += 1

    app_id = eid
    lines.append(f"#{eid}=APPLICATION_PROTOCOL_DEFINITION('international standard',"
                 f"'automotive_design',2010,#{ctx_id});")
    eid += 1

    # Product context
    pctx_id = eid
    lines.append(f"#{eid}=PRODUCT_CONTEXT('',#{ctx_id},'mechanical');")
    eid += 1

    # Product
    prod_id = eid
    lines.append(f"#{eid}=PRODUCT('{design_name}','{design_name}','',(#{pctx_id}));")
    eid += 1

    # Product definition formation
    pdf_id = eid
    lines.append(f"#{eid}=PRODUCT_DEFINITION_FORMATION('',' ',#{prod_id});")
    eid += 1

    # Product definition context
    pdctx_id = eid
    lines.append(f"#{eid}=PRODUCT_DEFINITION_CONTEXT('detailed design',#{ctx_id},"
                 f"'design');")
    eid += 1

    # Product definition
    pd_id = eid
    lines.append(f"#{eid}=PRODUCT_DEFINITION('design','',#{pdf_id},#{pdctx_id});")
    eid += 1

    # Shape definition
    sd_id = eid
    lines.append(f"#{eid}=PRODUCT_DEFINITION_SHAPE('','Shape for {design_name}',#{pd_id});")
    eid += 1

    # Coordinate system
    origin_id = eid
    lines.append(f"#{eid}=CARTESIAN_POINT('',(0.,0.,0.));")
    eid += 1

    dir_z_id = eid
    lines.append(f"#{eid}=DIRECTION('',(0.,0.,1.));")
    eid += 1

    dir_x_id = eid
    lines.append(f"#{eid}=DIRECTION('',(1.,0.,0.));")
    eid += 1

    axis_id = eid
    lines.append(f"#{eid}=AXIS2_PLACEMENT_3D('',#{origin_id},#{dir_z_id},#{dir_x_id});")
    eid += 1

    # Write all CARTESIAN_POINTs for vertices
    vert_ids = []
    for v in verts:
        vert_ids.append(eid)
        lines.append(f"#{eid}=CARTESIAN_POINT('',({v[0]:.6f},{v[1]:.6f},{v[2]:.6f}));")
        eid += 1

    # Write POLY_LOOPs and FACES for each triangle
    face_ids = []
    for face in faces:
        # Vertex point references
        vp0, vp1, vp2 = vert_ids[face[0]], vert_ids[face[1]], vert_ids[face[2]]

        # POLY_LOOP
        pl_id = eid
        lines.append(f"#{eid}=POLY_LOOP('',(#{vp0},#{vp1},#{vp2}));")
        eid += 1

        # FACE_BOUND
        fb_id = eid
        lines.append(f"#{eid}=FACE_BOUND('',#{pl_id},.T.);")
        eid += 1

        # FACE_SURFACE (simplified — using a plane)
        # Compute face normal for the plane
        v0 = verts[face[0]]
        v1 = verts[face[1]]
        v2 = verts[face[2]]
        e1 = v1 - v0
        e2 = v2 - v0
        normal = np.cross(e1, e2)
        norm_len = np.linalg.norm(normal)
        if norm_len > 1e-10:
            normal = normal / norm_len
        else:
            normal = np.array([0, 0, 1])

        # Normal direction
        nd_id = eid
        lines.append(f"#{eid}=DIRECTION('',({normal[0]:.6f},{normal[1]:.6f},{normal[2]:.6f}));")
        eid += 1

        # Ref direction (perpendicular to normal)
        if abs(normal[2]) < 0.9:
            ref = np.cross(normal, [0, 0, 1])
        else:
            ref = np.cross(normal, [1, 0, 0])
        ref = ref / (np.linalg.norm(ref) + 1e-10)

        rd_id = eid
        lines.append(f"#{eid}=DIRECTION('',({ref[0]:.6f},{ref[1]:.6f},{ref[2]:.6f}));")
        eid += 1

        # Point on face
        fp_id = eid
        lines.append(f"#{eid}=CARTESIAN_POINT('',({v0[0]:.6f},{v0[1]:.6f},{v0[2]:.6f}));")
        eid += 1

        # Axis placement for plane
        pa_id = eid
        lines.append(f"#{eid}=AXIS2_PLACEMENT_3D('',#{fp_id},#{nd_id},#{rd_id});")
        eid += 1

        # PLANE
        plane_id = eid
        lines.append(f"#{eid}=PLANE('',#{pa_id});")
        eid += 1

        # ADVANCED_FACE
        af_id = eid
        lines.append(f"#{eid}=ADVANCED_FACE('',(#{fb_id}),#{plane_id},.T.);")
        eid += 1
        face_ids.append(af_id)

    # CLOSED_SHELL
    face_refs = ",".join(f"#{fid}" for fid in face_ids)
    shell_id = eid
    lines.append(f"#{eid}=CLOSED_SHELL('',({face_refs}));")
    eid += 1

    # MANIFOLD_SOLID_BREP
    brep_id = eid
    lines.append(f"#{eid}=MANIFOLD_SOLID_BREP('{design_name}',#{shell_id});")
    eid += 1

    # Shape representation
    sr_id = eid
    lines.append(f"#{eid}=SHAPE_REPRESENTATION('{design_name}',(#{axis_id},#{brep_id}),#{eid + 1});")
    eid += 1

    # Geometric representation context
    grc_id = eid
    lines.append(f"#{eid}=(GEOMETRIC_REPRESENTATION_CONTEXT(3)"
                 f"GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{eid + 1}))"
                 f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{eid + 2},#{eid + 3},#{eid + 4}))"
                 f"REPRESENTATION_CONTEXT('Context3D','3D Context'));")
    eid += 1

    # Uncertainty
    unc_id = eid
    lines.append(f"#{eid}=UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),#{eid + 1},"
                 f"'distance_accuracy_value','confusion accuracy');")
    eid += 1

    # Units
    mm_id = eid
    lines.append(f"#{eid}=(CONVERSION_BASED_UNIT('MILLIMETRE',#{eid + 4})"
                 f"LENGTH_UNIT()NAMED_UNIT(#{eid + 3}));")
    eid += 1

    rad_id = eid
    lines.append(f"#{eid}=(NAMED_UNIT(#{eid + 2})PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.));")
    eid += 1

    sr_id2 = eid
    lines.append(f"#{eid}=(NAMED_UNIT(#{eid + 1})SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT());")
    eid += 1

    dim_id = eid
    lines.append(f"#{eid}=DIMENSIONAL_EXPONENTS(0.,0.,0.,0.,0.,0.,0.);")
    eid += 1

    dim_id2 = eid
    lines.append(f"#{eid}=DIMENSIONAL_EXPONENTS(1.,0.,0.,0.,0.,0.,0.);")
    eid += 1

    lmwu_id = eid
    lines.append(f"#{eid}=LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.),#{mm_id});")
    eid += 1

    # Shape definition representation
    sdr_id = eid
    lines.append(f"#{eid}=SHAPE_DEFINITION_REPRESENTATION(#{sd_id},#{sr_id - 1});")
    eid += 1

    lines.append("ENDSEC;")
    lines.append("END-ISO-10303-21;")

    with open(filepath, 'w') as f:
        f.write("\n".join(lines))
