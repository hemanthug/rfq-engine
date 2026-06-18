from __future__ import annotations

import math
from collections import Counter

from app.schemas.features import EdgeAnalysis, FaceAdjacency, FaceAnalysis, HoleFeature, PocketFeature, RejectedFeatureCandidate


DETECTOR_VERSIONS = {
    "hole_recognizer": "conservative_cylindrical_holes_v2",
    "pocket_recognizer": "simple_planar_pockets_v1",
    "complexity_score": "deterministic_complexity_v1",
}


DEFERRED_FEATURE_TYPES = [
    "counterbores",
    "countersinks",
    "threads",
    "tapped_holes",
    "hole_patterns",
    "interacting_pockets",
    "slots",
    "bosses",
    "fillets",
    "chamfers",
    "bends",
    "sheet_metal_classification",
    "draft_angle",
    "undercuts",
    "parting_lines",
    "setup_orientation",
    "ml_feature_segmentation",
]


def _face_lookup(faces: list[FaceAnalysis]) -> dict[str, FaceAnalysis]:
    return {face.face_id: face for face in faces}


def _edge_lookup(edges: list[EdgeAnalysis]) -> dict[str, EdgeAnalysis]:
    return {edge.edge_id: edge for edge in edges}


def _axis_key(face: FaceAnalysis) -> tuple[float, ...]:
    origin = face.axis_origin or [0.0, 0.0, 0.0]
    direction = face.axis_direction or [0.0, 0.0, 0.0]
    radius = face.radius or 0.0
    return tuple(round(value, 5) for value in [*origin, *direction, radius])


def recognize_holes(
    faces: list[FaceAnalysis],
    edges: list[EdgeAnalysis],
) -> tuple[list[HoleFeature], list[RejectedFeatureCandidate]]:
    face_by_id = _face_lookup(faces)
    edge_by_id = _edge_lookup(edges)
    holes: list[HoleFeature] = []
    rejected: list[RejectedFeatureCandidate] = []
    cylinder_faces = [face for face in faces if face.surface_type == "cylinder" and face.radius]
    grouped: dict[tuple[float, ...], list[FaceAnalysis]] = {}
    diameter_counts = Counter(round(float(face.radius or 0.0) * 2.0, 3) for face in cylinder_faces)
    bbox_span = _axis_span(faces)

    for face in cylinder_faces:
        grouped.setdefault(_axis_key(face), []).append(face)

    for group_index, group in enumerate(grouped.values(), start=1):
        primary = group[0]
        diameter = float(primary.radius or 0.0) * 2.0
        rounded_diameter = round(diameter, 3)
        circular_edges = [
            edge_by_id[edge_id]
            for face in group
            for edge_id in face.edge_ids
            if edge_id in edge_by_id and edge_by_id[edge_id].curve_type == "circle"
        ]
        adjacent_face_ids = sorted(
            {
                adjacent_face_id
                for edge in circular_edges
                for adjacent_face_id in edge.adjacent_face_ids
                if adjacent_face_id not in {face.face_id for face in group}
            }
        )
        all_adjacent_face_ids = sorted(
            {
                adjacent_face_id
                for face in group
                for edge_id in face.edge_ids
                if edge_id in edge_by_id
                for adjacent_face_id in edge_by_id[edge_id].adjacent_face_ids
                if adjacent_face_id not in {group_face.face_id for group_face in group}
            }
        )
        adjacent_faces = [face_by_id[face_id] for face_id in adjacent_face_ids if face_id in face_by_id]
        all_adjacent_faces = [face_by_id[face_id] for face_id in all_adjacent_face_ids if face_id in face_by_id]
        inner_loop_planar_faces = [
            face
            for face in adjacent_faces
            if face.surface_type == "plane" and face.inner_wire_count > 0
        ]
        planar_cap_faces = [
            face
            for face in adjacent_faces
            if face.surface_type == "plane"
            and face.inner_wire_count == 0
            and face.edge_ids
            and face.area <= math.pi * float(primary.radius or 0.0) ** 2 * 1.25
        ]
        non_cap_planar_side_faces = [
            face
            for face in all_adjacent_faces
            if face.surface_type == "plane"
            and face.inner_wire_count == 0
            and face not in planar_cap_faces
        ]

        if len(circular_edges) < 2:
            continue
        if not inner_loop_planar_faces:
            continue
        if len(inner_loop_planar_faces) >= 2 and len(non_cap_planar_side_faces) >= 2:
            rejected.append(
                RejectedFeatureCandidate(
                    candidate_type="cylindrical_hole",
                    face_ids=[face.face_id for face in group],
                    reason="external_profile_cylindrical_flank",
                    evidence=[
                        "cylindrical_wall",
                        "two_or_more_planar_opening_faces",
                        "two_or_more_non_cap_planar_side_faces",
                    ],
                )
            )
            continue
        if _is_repeated_tooth_profile_group(group, rounded_diameter, diameter_counts):
            rejected.append(
                RejectedFeatureCandidate(
                    candidate_type="cylindrical_hole",
                    face_ids=[face.face_id for face in group],
                    reason="tooth_root_cylindrical_arc",
                    evidence=[
                        "repeated_matching_diameter",
                        "small_partial_cylindrical_faces",
                        "profile_arc_not_internal_void",
                    ],
                )
            )
            continue
        if _is_exterior_body_cylinder(group, diameter, bbox_span):
            rejected.append(
                RejectedFeatureCandidate(
                    candidate_type="cylindrical_hole",
                    face_ids=[face.face_id for face in group],
                    reason="external_profile_cylinder",
                    evidence=[
                        "diameter_matches_part_envelope",
                        "exterior_body_surface_not_internal_void",
                    ],
                )
            )
            continue

        hole_type = "blind" if len(planar_cap_faces) == 1 else "through"
        if hole_type == "through" and len(inner_loop_planar_faces) < 2:
            continue
        depth = None
        if primary.radius and primary.area > 0:
            depth = primary.area / (2.0 * math.pi * primary.radius)

        confidence = 0.9 if hole_type == "blind" else 0.82
        if len(group) > 1:
            confidence -= 0.1
        evidence = [
            "cylindrical_wall",
            "circular_boundary_edges",
            "planar_bottom_cap" if hole_type == "blind" else "no_small_planar_bottom_cap",
        ]

        holes.append(
            HoleFeature(
                feature_id=f"hole_{group_index:04d}",
                hole_type=hole_type,
                face_ids=[face.face_id for face in group] + [face.face_id for face in planar_cap_faces],
                diameter=diameter,
                axis_origin=primary.axis_origin or [0.0, 0.0, 0.0],
                axis_direction=primary.axis_direction or [0.0, 0.0, 1.0],
                depth=depth,
                confidence=max(0.0, min(1.0, confidence)),
                evidence=evidence,
            )
        )

    return holes, rejected


def _axis_span(faces: list[FaceAnalysis]) -> float:
    origins = [face.axis_origin for face in faces if face.axis_origin]
    if not origins:
        return 0.0
    values = [coordinate for origin in origins for coordinate in origin]
    return max(values) - min(values)


def _is_repeated_tooth_profile_group(
    group: list[FaceAnalysis],
    rounded_diameter: float,
    diameter_counts: Counter,
) -> bool:
    if diameter_counts[rounded_diameter] < 12:
        return False
    if len(group) > 12:
        return True
    max_group_area = max((face.area for face in group), default=0.0)
    return rounded_diameter <= 5.0 and max_group_area <= 125.0


def _is_exterior_body_cylinder(group: list[FaceAnalysis], diameter: float, bbox_span: float) -> bool:
    if bbox_span <= 0:
        return False
    if diameter < bbox_span * 0.98:
        return False
    total_area = sum(face.area for face in group)
    return total_area >= 100.0


def recognize_pockets(faces: list[FaceAnalysis], adjacency: list[FaceAdjacency]) -> list[PocketFeature]:
    face_by_id = _face_lookup(faces)
    max_plane_area = max((face.area for face in faces if face.surface_type == "plane"), default=0.0)
    neighbor_ids_by_face: dict[str, set[str]] = {face.face_id: set() for face in faces}

    for relation in adjacency:
        if len(relation.face_ids) == 2:
            left, right = relation.face_ids
            neighbor_ids_by_face.setdefault(left, set()).add(right)
            neighbor_ids_by_face.setdefault(right, set()).add(left)

    pockets: list[PocketFeature] = []
    for face in faces:
        if face.surface_type != "plane" or face.inner_wire_count > 0:
            continue
        if face.area < 10.0:
            continue
        if max_plane_area and face.area >= max_plane_area * 0.9:
            continue
        if any(face_by_id[neighbor_id].inner_wire_count > 0 for neighbor_id in neighbor_ids_by_face.get(face.face_id, set())):
            continue
        side_faces = [
            face_by_id[neighbor_id]
            for neighbor_id in sorted(neighbor_ids_by_face.get(face.face_id, set()))
            if neighbor_id in face_by_id and face_by_id[neighbor_id].surface_type == "plane"
        ]
        rim_supported_side_faces = [
            side_face
            for side_face in side_faces
            if any(
                rim_neighbor_id != face.face_id
                and face_by_id[rim_neighbor_id].inner_wire_count > 0
                for rim_neighbor_id in neighbor_ids_by_face.get(side_face.face_id, set())
            )
        ]
        if len(rim_supported_side_faces) < 3:
            continue

        pockets.append(
            PocketFeature(
                feature_id=f"pocket_{len(pockets) + 1:04d}",
                pocket_type="candidate_planar_bottom",
                bottom_face_id=face.face_id,
                side_face_ids=[side_face.face_id for side_face in rim_supported_side_faces],
                depth=None,
                confidence=0.58 if len(rim_supported_side_faces) == 3 else 0.68,
                evidence=["planar_bottom_face", "rim_supported_sidewalls", "heuristic_candidate"],
            )
        )

    if len(pockets) > 4:
        return []

    return pockets
