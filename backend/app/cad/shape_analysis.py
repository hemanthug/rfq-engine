from __future__ import annotations

from typing import Any

from app.schemas.cad import BoundingBox, MassProperties, ShapeValidity, ToleranceSummary, TopologyCounts


TOPOLOGY_TYPES = {
    "vertices": "TopAbs_VERTEX",
    "edges": "TopAbs_EDGE",
    "wires": "TopAbs_WIRE",
    "faces": "TopAbs_FACE",
    "shells": "TopAbs_SHELL",
    "solids": "TopAbs_SOLID",
    "comp_solids": "TopAbs_COMPSOLID",
    "compounds": "TopAbs_COMPOUND",
}


def _import_occ_modules() -> dict[str, Any]:
    from OCC.Core import BRepBndLib, BRepGProp
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.ShapeAnalysis import ShapeAnalysis_ShapeTolerance
    from OCC.Core.TopAbs import (
        TopAbs_COMPOUND,
        TopAbs_COMPSOLID,
        TopAbs_EDGE,
        TopAbs_FACE,
        TopAbs_SHELL,
        TopAbs_SOLID,
        TopAbs_VERTEX,
        TopAbs_WIRE,
    )
    from OCC.Core.TopExp import TopExp_Explorer

    return {
        "BRepBndLib": BRepBndLib,
        "BRepGProp": BRepGProp,
        "Bnd_Box": Bnd_Box,
        "BRepCheck_Analyzer": BRepCheck_Analyzer,
        "GProp_GProps": GProp_GProps,
        "ShapeAnalysis_ShapeTolerance": ShapeAnalysis_ShapeTolerance,
        "TopExp_Explorer": TopExp_Explorer,
        "top_abs_values": {
            "TopAbs_VERTEX": TopAbs_VERTEX,
            "TopAbs_EDGE": TopAbs_EDGE,
            "TopAbs_WIRE": TopAbs_WIRE,
            "TopAbs_FACE": TopAbs_FACE,
            "TopAbs_SHELL": TopAbs_SHELL,
            "TopAbs_SOLID": TopAbs_SOLID,
            "TopAbs_COMPSOLID": TopAbs_COMPSOLID,
            "TopAbs_COMPOUND": TopAbs_COMPOUND,
        },
    }


def _call_occ_function(module: Any, modern_name: str, legacy_name: str, *args: Any) -> Any:
    holder_name = legacy_name.split("_", 1)[0]
    holder = getattr(module, holder_name, None)
    if holder is not None and hasattr(holder, modern_name):
        return getattr(holder, modern_name)(*args)
    if hasattr(module, modern_name):
        return getattr(module, modern_name)(*args)
    if hasattr(module, legacy_name):
        return getattr(module, legacy_name)(*args)
    raise AttributeError(f"Neither {modern_name} nor {legacy_name} exists on {module!r}")


def count_topology(shape: Any) -> TopologyCounts:
    modules = _import_occ_modules()
    explorer_type = modules["TopExp_Explorer"]
    top_abs_values = modules["top_abs_values"]
    counts: dict[str, int] = {}

    for output_name, top_abs_name in TOPOLOGY_TYPES.items():
        explorer = explorer_type(shape, top_abs_values[top_abs_name])
        count = 0
        while explorer.More():
            count += 1
            explorer.Next()
        counts[output_name] = count

    return TopologyCounts(**counts)


def compute_bounding_box(shape: Any) -> BoundingBox:
    modules = _import_occ_modules()
    box = modules["Bnd_Box"]()
    _call_occ_function(modules["BRepBndLib"], "Add", "brepbndlib_Add", shape, box)

    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return BoundingBox(
        minimum=[float(xmin), float(ymin), float(zmin)],
        maximum=[float(xmax), float(ymax), float(zmax)],
        size=[float(xmax - xmin), float(ymax - ymin), float(zmax - zmin)],
    )


def compute_mass_properties(shape: Any) -> MassProperties:
    modules = _import_occ_modules()
    brep_gprop = modules["BRepGProp"]
    gprops_type = modules["GProp_GProps"]

    volume_props = gprops_type()
    _call_occ_function(
        brep_gprop,
        "VolumeProperties",
        "brepgprop_VolumeProperties",
        shape,
        volume_props,
    )

    surface_props = gprops_type()
    _call_occ_function(
        brep_gprop,
        "SurfaceProperties",
        "brepgprop_SurfaceProperties",
        shape,
        surface_props,
    )

    return MassProperties(volume=float(volume_props.Mass()), surface_area=float(surface_props.Mass()))


def check_shape_validity(shape: Any) -> ShapeValidity:
    modules = _import_occ_modules()
    analyzer = modules["BRepCheck_Analyzer"](shape)
    return ShapeValidity(is_valid=bool(analyzer.IsValid()))


def summarize_tolerances(shape: Any) -> ToleranceSummary:
    modules = _import_occ_modules()
    tolerance_tool = modules["ShapeAnalysis_ShapeTolerance"]()
    return ToleranceSummary(
        minimum=float(tolerance_tool.Tolerance(shape, -1)),
        average=float(tolerance_tool.Tolerance(shape, 0)),
        maximum=float(tolerance_tool.Tolerance(shape, 1)),
    )


def classify_shape(topology: TopologyCounts) -> str:
    if topology.solids == 1 and topology.comp_solids == 0:
        return "single_solid"
    if topology.solids > 1:
        return "multi_solid"
    if topology.comp_solids > 0:
        return "compound_solid"
    if topology.shells > 0:
        return "shell_only"
    if topology.faces > 0:
        return "face_only"
    if topology.compounds > 0:
        return "compound_without_solid"
    return "unknown"
