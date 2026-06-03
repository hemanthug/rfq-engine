from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TopologyIndex:
    faces: list[Any]
    edges: list[Any]
    face_ids: dict[int, str]
    edge_ids: dict[int, str]
    face_edges: dict[str, list[str]]
    edge_faces: dict[str, list[str]]


def _import_occ_modules() -> dict[str, Any]:
    from OCC.Core import TopAbs, TopExp, TopoDS
    from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_IndexedMapOfShape

    return {
        "TopAbs": TopAbs,
        "TopExp": TopExp,
        "TopoDS": TopoDS,
        "TopTools_IndexedDataMapOfShapeListOfShape": TopTools_IndexedDataMapOfShapeListOfShape,
        "TopTools_IndexedMapOfShape": TopTools_IndexedMapOfShape,
    }


def _shape_key(shape: Any) -> int:
    return int(hash(shape))


def _explore(shape: Any, shape_type: Any, caster: Any) -> list[Any]:
    modules = _import_occ_modules()
    shape_map = modules["TopTools_IndexedMapOfShape"]()
    modules["TopExp"].topexp.MapShapes(shape, shape_type, shape_map)
    shapes: list[Any] = []
    for index in range(1, int(shape_map.Size()) + 1):
        shapes.append(caster(shape_map.FindKey(index)))
    return shapes


def build_topology_index(shape: Any) -> TopologyIndex:
    modules = _import_occ_modules()
    top_abs = modules["TopAbs"]
    topods = modules["TopoDS"].topods

    faces = _explore(shape, top_abs.TopAbs_FACE, topods.Face)
    edges = _explore(shape, top_abs.TopAbs_EDGE, topods.Edge)
    face_ids = {_shape_key(face): f"face_{index:04d}" for index, face in enumerate(faces, start=1)}
    edge_ids = {_shape_key(edge): f"edge_{index:04d}" for index, edge in enumerate(edges, start=1)}

    edge_face_map = modules["TopTools_IndexedDataMapOfShapeListOfShape"]()
    modules["TopExp"].topexp.MapShapesAndUniqueAncestors(
        shape,
        top_abs.TopAbs_EDGE,
        top_abs.TopAbs_FACE,
        edge_face_map,
    )

    edge_faces: dict[str, list[str]] = {}
    for index in range(1, int(edge_face_map.Size()) + 1):
        edge = topods.Edge(edge_face_map.FindKey(index))
        edge_id = edge_ids.get(_shape_key(edge))
        if edge_id is None:
            continue
        faces_for_edge = edge_face_map.FindFromIndex(index)
        adjacent_face_ids: list[str] = []
        for adjacent_face in faces_for_edge:
            face = topods.Face(adjacent_face)
            face_id = face_ids.get(_shape_key(face))
            if face_id is not None:
                adjacent_face_ids.append(face_id)
        edge_faces[edge_id] = sorted(set(adjacent_face_ids))

    face_edges: dict[str, list[str]] = {face_id: [] for face_id in face_ids.values()}
    for edge_id, adjacent_face_ids in edge_faces.items():
        for face_id in adjacent_face_ids:
            face_edges.setdefault(face_id, []).append(edge_id)
    face_edges = {face_id: sorted(set(edge_ids_for_face)) for face_id, edge_ids_for_face in face_edges.items()}

    return TopologyIndex(
        faces=faces,
        edges=edges,
        face_ids=face_ids,
        edge_ids=edge_ids,
        face_edges=face_edges,
        edge_faces=edge_faces,
    )
