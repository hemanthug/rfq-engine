from __future__ import annotations

from typing import Any

from app.cad.shape_analysis import _call_occ_function
from app.cad.topology import TopologyIndex
from app.schemas.features import FaceAnalysis


SURFACE_TYPE_NAMES = {
    "GeomAbs_Plane": "plane",
    "GeomAbs_Cylinder": "cylinder",
    "GeomAbs_Cone": "cone",
    "GeomAbs_Sphere": "sphere",
    "GeomAbs_Torus": "torus",
    "GeomAbs_BezierSurface": "bezier_surface",
    "GeomAbs_BSplineSurface": "bspline_surface",
    "GeomAbs_SurfaceOfRevolution": "surface_of_revolution",
    "GeomAbs_SurfaceOfExtrusion": "surface_of_extrusion",
    "GeomAbs_OffsetSurface": "offset_surface",
    "GeomAbs_OtherSurface": "other",
}

SURFACE_TYPE_NUMBERS = {
    0: "plane",
    1: "cylinder",
    2: "cone",
    3: "sphere",
    4: "torus",
    5: "bezier_surface",
    6: "bspline_surface",
    7: "surface_of_revolution",
    8: "surface_of_extrusion",
    9: "offset_surface",
    10: "other",
}


def _import_occ_modules() -> dict[str, Any]:
    from OCC.Core import BRepGProp, BRepTools, TopAbs, TopExp
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepLProp import BRepLProp_SLProps
    from OCC.Core.GProp import GProp_GProps

    return {
        "BRepAdaptor_Surface": BRepAdaptor_Surface,
        "BRepGProp": BRepGProp,
        "BRepLProp_SLProps": BRepLProp_SLProps,
        "BRepTools": BRepTools,
        "GProp_GProps": GProp_GProps,
        "TopAbs": TopAbs,
        "TopExp": TopExp,
    }


def _vec3_from_dir(direction: Any) -> list[float]:
    return [float(direction.X()), float(direction.Y()), float(direction.Z())]


def _vec3_from_point(point: Any) -> list[float]:
    return [float(point.X()), float(point.Y()), float(point.Z())]


def _surface_type_name(surface_type: Any) -> str:
    if isinstance(surface_type, int):
        return SURFACE_TYPE_NUMBERS.get(surface_type, "other")
    return SURFACE_TYPE_NAMES.get(getattr(surface_type, "name", str(surface_type)), "other")


def _face_area(face: Any, modules: dict[str, Any]) -> float:
    props = modules["GProp_GProps"]()
    _call_occ_function(modules["BRepGProp"], "SurfaceProperties", "brepgprop_SurfaceProperties", face, props)
    return float(props.Mass())


def _wire_counts(face: Any, modules: dict[str, Any]) -> tuple[int, int]:
    top_exp = modules["TopExp"]
    top_abs = modules["TopAbs"]
    explorer = top_exp.TopExp_Explorer(face, top_abs.TopAbs_WIRE)
    wire_count = 0
    while explorer.More():
        wire_count += 1
        explorer.Next()
    return (1 if wire_count else 0, max(0, wire_count - 1))


def analyze_faces(topology: TopologyIndex) -> list[FaceAnalysis]:
    modules = _import_occ_modules()
    analyses: list[FaceAnalysis] = []

    for face in topology.faces:
        face_id = topology.face_ids[int(hash(face))]
        adaptor = modules["BRepAdaptor_Surface"](face)
        surface_type = _surface_type_name(adaptor.GetType())
        outer_wire_count, inner_wire_count = _wire_counts(face, modules)
        normal: list[float] | None = None
        axis_origin: list[float] | None = None
        axis_direction: list[float] | None = None
        radius: float | None = None
        semi_angle: float | None = None

        if surface_type == "plane":
            plane = adaptor.Plane()
            normal = _vec3_from_dir(plane.Axis().Direction())
        elif surface_type == "cylinder":
            cylinder = adaptor.Cylinder()
            axis_origin = _vec3_from_point(cylinder.Axis().Location())
            axis_direction = _vec3_from_dir(cylinder.Axis().Direction())
            radius = float(cylinder.Radius())
        elif surface_type == "cone":
            cone = adaptor.Cone()
            axis_origin = _vec3_from_point(cone.Axis().Location())
            axis_direction = _vec3_from_dir(cone.Axis().Direction())
            radius = float(cone.RefRadius())
            semi_angle = float(cone.SemiAngle())
        else:
            u = (float(adaptor.FirstUParameter()) + float(adaptor.LastUParameter())) / 2.0
            v = (float(adaptor.FirstVParameter()) + float(adaptor.LastVParameter())) / 2.0
            props = modules["BRepLProp_SLProps"](adaptor, u, v, 1, 1e-7)
            if props.IsNormalDefined():
                normal = _vec3_from_dir(props.Normal())

        analyses.append(
            FaceAnalysis(
                face_id=face_id,
                surface_type=surface_type,
                area=_face_area(face, modules),
                tolerance=float(adaptor.Tolerance()),
                edge_ids=topology.face_edges.get(face_id, []),
                inner_wire_count=inner_wire_count,
                outer_wire_count=outer_wire_count,
                normal=normal,
                axis_origin=axis_origin,
                axis_direction=axis_direction,
                radius=radius,
                semi_angle=semi_angle,
            )
        )

    return analyses
