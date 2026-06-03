from __future__ import annotations

from typing import Any

from app.cad.shape_analysis import _call_occ_function
from app.cad.topology import TopologyIndex
from app.schemas.features import EdgeAnalysis


CURVE_TYPE_NAMES = {
    "GeomAbs_Line": "line",
    "GeomAbs_Circle": "circle",
    "GeomAbs_Ellipse": "ellipse",
    "GeomAbs_Hyperbola": "hyperbola",
    "GeomAbs_Parabola": "parabola",
    "GeomAbs_BezierCurve": "bezier_curve",
    "GeomAbs_BSplineCurve": "bspline_curve",
    "GeomAbs_OffsetCurve": "offset_curve",
    "GeomAbs_OtherCurve": "other",
}

CURVE_TYPE_NUMBERS = {
    0: "line",
    1: "circle",
    2: "ellipse",
    3: "hyperbola",
    4: "parabola",
    5: "bezier_curve",
    6: "bspline_curve",
    7: "offset_curve",
    8: "other",
}


def _import_occ_modules() -> dict[str, Any]:
    from OCC.Core import BRepGProp
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GProp import GProp_GProps

    return {
        "BRepAdaptor_Curve": BRepAdaptor_Curve,
        "BRepGProp": BRepGProp,
        "GProp_GProps": GProp_GProps,
    }


def _curve_type_name(curve_type: Any) -> str:
    if isinstance(curve_type, int):
        return CURVE_TYPE_NUMBERS.get(curve_type, "other")
    return CURVE_TYPE_NAMES.get(getattr(curve_type, "name", str(curve_type)), "other")


def _edge_length(edge: Any, modules: dict[str, Any]) -> float:
    props = modules["GProp_GProps"]()
    _call_occ_function(modules["BRepGProp"], "LinearProperties", "brepgprop_LinearProperties", edge, props)
    return float(props.Mass())


def _vec3_from_point(point: Any) -> list[float]:
    return [float(point.X()), float(point.Y()), float(point.Z())]


def analyze_edges(topology: TopologyIndex) -> list[EdgeAnalysis]:
    modules = _import_occ_modules()
    analyses: list[EdgeAnalysis] = []

    for edge in topology.edges:
        edge_id = topology.edge_ids[int(hash(edge))]
        adaptor = modules["BRepAdaptor_Curve"](edge)
        curve_type = _curve_type_name(adaptor.GetType())
        radius: float | None = None
        center: list[float] | None = None
        if curve_type == "circle":
            circle = adaptor.Circle()
            radius = float(circle.Radius())
            center = _vec3_from_point(circle.Location())

        analyses.append(
            EdgeAnalysis(
                edge_id=edge_id,
                curve_type=curve_type,
                length=_edge_length(edge, modules),
                adjacent_face_ids=topology.edge_faces.get(edge_id, []),
                radius=radius,
                center=center,
            )
        )

    return analyses
