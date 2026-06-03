from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.schemas.features import FaceAnalysis, FeatureExtractionResult


@dataclass(frozen=True)
class BendCandidate:
    face_id: str
    radius_mm: float
    area_mm2: float
    angle_rad: float
    length_mm: float


def raw_thin_shell_thickness_mm(features: FeatureExtractionResult) -> float:
    volume = features.source.mass_properties.volume
    surface_area = features.source.mass_properties.surface_area
    if volume <= 0 or surface_area <= 0:
        return 0.0
    return float((2.0 * volume) / surface_area)


def bend_candidates(features: FeatureExtractionResult, thickness_mm: float) -> list[BendCandidate]:
    if thickness_mm <= 0:
        return []

    face_by_id = {face.face_id: face for face in features.faces}
    edge_by_id = {edge.edge_id: edge for edge in features.edges}
    hole_face_ids = {face_id for hole in features.holes for face_id in hole.face_ids}
    rejected_face_ids = {
        face_id
        for candidate in features.diagnostics.rejected_candidates
        for face_id in candidate.face_ids
    }
    candidates: list[BendCandidate] = []
    for face in features.faces:
        if face.surface_type != "cylinder" or face.radius is None:
            continue
        if face.face_id in hole_face_ids or face.face_id in rejected_face_ids:
            continue
        if not (thickness_mm * 0.3 <= face.radius <= thickness_mm * 1.5):
            continue
        if face.area < max(20.0, thickness_mm * thickness_mm * 6.0):
            continue

        adjacent_planes = _adjacent_planes(face, face_by_id, edge_by_id)
        if len(adjacent_planes) < 2:
            continue
        angle_rad = _bend_angle_from_planes(adjacent_planes)
        length_mm = face.area / max(1e-6, face.radius * angle_rad)
        if length_mm < max(5.0, thickness_mm * 2.0):
            continue
        candidates.append(
            BendCandidate(
                face_id=face.face_id,
                radius_mm=float(face.radius),
                area_mm2=float(face.area),
                angle_rad=float(angle_rad),
                length_mm=float(length_mm),
            )
        )
    return candidates


def estimated_cut_length_mm(features: FeatureExtractionResult) -> tuple[float, str]:
    boundary_edge_length = sum(edge.length for edge in features.edges if len(edge.adjacent_face_ids) <= 1)
    if boundary_edge_length > 0:
        return float(boundary_edge_length), "boundary_edges"
    ordered = sorted(features.source.bounding_box.size)
    return float(2.0 * (ordered[1] + ordered[2])), "bounding_box_perimeter"


def one_sided_planar_area_mm2(features: FeatureExtractionResult) -> tuple[float, str]:
    planar_area = sum(face.area for face in features.faces if face.surface_type == "plane")
    if planar_area > 0:
        return float(planar_area / 2.0), "half_planar_face_area"
    return 0.0, "not_available"


def neutral_axis_unfold_metrics(
    features: FeatureExtractionResult,
    thickness_mm: float,
    k_factor: float,
) -> dict[str, Any]:
    bends = bend_candidates(features, thickness_mm)
    planar_area_mm2, planar_method = one_sided_planar_area_mm2(features)
    bend_allowance_area_mm2 = 0.0
    bend_allowance_total_mm = 0.0
    bend_deduction_total_mm = 0.0
    for bend in bends:
        allowance_mm = bend.angle_rad * (bend.radius_mm + k_factor * thickness_mm)
        deduction_mm = 2.0 * (bend.radius_mm + thickness_mm) * math.tan(bend.angle_rad / 2.0) - allowance_mm
        bend_allowance_total_mm += allowance_mm
        bend_deduction_total_mm += max(0.0, deduction_mm)
        bend_allowance_area_mm2 += allowance_mm * bend.length_mm

    fallback_area_mm2 = _volume_flat_area_mm2(features, thickness_mm)
    topology_area_mm2 = planar_area_mm2 + bend_allowance_area_mm2
    if topology_area_mm2 > 0:
        flat_area_mm2 = topology_area_mm2
        method = "planar_faces_plus_bend_allowance"
        confidence = 0.72
        if fallback_area_mm2 > 0:
            ratio = topology_area_mm2 / fallback_area_mm2
            if ratio < 0.45 or ratio > 2.2:
                flat_area_mm2 = fallback_area_mm2
                method = "volume_divided_by_thickness"
                confidence = 0.5
    else:
        flat_area_mm2 = fallback_area_mm2
        method = "volume_divided_by_thickness"
        confidence = 0.45

    return {
        "bend_candidate_count": float(len(bends)),
        "bend_allowance_total_mm": float(bend_allowance_total_mm),
        "bend_deduction_total_mm": float(bend_deduction_total_mm),
        "bend_allowance_area_cm2": float(bend_allowance_area_mm2 / 100.0),
        "flat_pattern_area_cm2": float(flat_area_mm2 / 100.0),
        "flat_pattern_estimation_method": method,
        "flat_pattern_confidence": float(confidence),
        "planar_area_method": planar_method,
        "k_factor": float(k_factor),
    }


def _volume_flat_area_mm2(features: FeatureExtractionResult, thickness_mm: float) -> float:
    if thickness_mm <= 0:
        return 0.0
    return float(features.source.mass_properties.volume / thickness_mm)


def _adjacent_planes(
    face: FaceAnalysis,
    face_by_id: dict[str, FaceAnalysis],
    edge_by_id: dict[str, Any],
) -> list[FaceAnalysis]:
    adjacent_face_ids = {
        adjacent_face_id
        for edge_id in face.edge_ids
        for edge in [edge_by_id.get(edge_id)]
        if edge is not None
        for adjacent_face_id in edge.adjacent_face_ids
        if adjacent_face_id != face.face_id
    }
    return [
        face_by_id[face_id]
        for face_id in adjacent_face_ids
        if face_id in face_by_id and face_by_id[face_id].surface_type == "plane"
    ]


def _bend_angle_from_planes(adjacent_planes: list[FaceAnalysis]) -> float:
    normals = [plane.normal for plane in adjacent_planes if plane.normal is not None]
    best = 0.0
    for index, left in enumerate(normals):
        for right in normals[index + 1 :]:
            dot = sum(left[axis] * right[axis] for axis in range(3))
            dot = max(-1.0, min(1.0, abs(dot)))
            best = max(best, math.acos(dot))
    if best <= math.radians(5.0):
        best = math.radians(90.0)
    return max(math.radians(15.0), min(math.radians(170.0), best))
