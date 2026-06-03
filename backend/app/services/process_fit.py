from __future__ import annotations

from app.schemas.features import FeatureExtractionResult
from app.schemas.recommendations import ProcessFitResult, RankedProcessRecommendation
from app.services.sheet_metal_geometry import bend_candidates, estimated_cut_length_mm, raw_thin_shell_thickness_mm


PROCESS_LABELS = {
    "cnc": "CNC",
    "injection_molding": "Injection molding",
    "3d_printing": "3D printing",
    "sheet_metal": "Sheet metal",
}


class ProcessFitRecommender:
    def recommend(self, features: FeatureExtractionResult, quantity: int | None = None) -> ProcessFitResult:
        signals = sheet_metal_signals(features)
        sheet_metal = self._sheet_metal(signals)
        cnc = self._cnc(signals)
        if self._is_sheet_metal_candidate(signals):
            ranked = [sheet_metal, cnc]
        else:
            ranked = [cnc, sheet_metal]
        recommended = ranked[0]
        warnings = [
            "process_recommendation_is_budgetary",
            "manufacturing_method_requires_engineering_review",
        ]
        return ProcessFitResult(
            recommended_process=recommended.process,
            ranked_processes=ranked,
            confidence=recommended.confidence,
            reasons=recommended.reasons[:3],
            warnings=warnings,
            signals=signals,
        )

    def _cnc(self, signals: dict[str, float]) -> RankedProcessRecommendation:
        score = 70.0
        if self._is_sheet_metal_candidate(signals):
            score = 55.0
        reasons = ["CNC is the default quote path unless geometry is confidently sheet-metal-like."]
        return self._process("cnc", score, reasons, [])

    def _sheet_metal(self, signals: dict[str, float]) -> RankedProcessRecommendation:
        reasons = ["Thin shell geometry resembles a sheet-metal candidate."]
        warnings = []
        if signals["bend_candidate_count"] == 0:
            warnings.append("no_bends_detected_flat_sheet_candidate")
        return self._process("sheet_metal", signals["sheet_metal_confidence_score"], reasons, warnings)

    def _is_sheet_metal_candidate(self, signals: dict[str, float]) -> bool:
        has_bends = signals["bend_candidate_count"] > 0
        flat_sheet_like = signals["thinness_ratio"] <= 0.08 and signals["planar_face_ratio"] >= 0.75
        return (
            signals["estimated_thickness_mm"] <= 6.0
            and (has_bends or flat_sheet_like)
            and signals["sheet_metal_confidence_score"] >= 70.0
        )

    def _process(
        self,
        process: str,
        score: float,
        reasons: list[str],
        warnings: list[str],
    ) -> RankedProcessRecommendation:
        clamped = round(max(0.0, min(100.0, score)), 1)
        if clamped >= 75.0:
            confidence = "high"
        elif clamped >= 55.0:
            confidence = "medium"
        else:
            confidence = "low"
        return RankedProcessRecommendation(
            process=process,
            label=PROCESS_LABELS[process],
            score=clamped,
            confidence=confidence,
            reasons=reasons,
            warnings=warnings,
        )


def sheet_metal_signals(features: FeatureExtractionResult) -> dict[str, float]:
    bbox = features.source.bounding_box.size
    max_dim = max(bbox)
    min_dim = min(bbox)
    volume = max(0.0, features.source.mass_properties.volume)
    surface_area = max(1.0, features.source.mass_properties.surface_area)
    projected_area = max(bbox[0] * bbox[1], bbox[0] * bbox[2], bbox[1] * bbox[2])
    non_planar_ratio = features.complexity.signals.get("non_planar_face_ratio", 0.0)
    planar_ratio = 1.0 - non_planar_ratio
    profile_count = sum(
        1
        for candidate in features.diagnostics.rejected_candidates
        if candidate.reason in {"tooth_root_cylindrical_arc", "external_profile_cylindrical_flank"}
    )
    estimated_thickness = raw_thin_shell_thickness_mm(features)
    bend_count = len(bend_candidates(features, estimated_thickness))
    flat_area_cm2 = _flat_pattern_area_cm2(volume, estimated_thickness, projected_area)
    cut_length_mm, _cut_length_method = estimated_cut_length_mm(features)
    score = 0.0
    if estimated_thickness <= 6.0:
        score += 35.0
    if bend_count > 0:
        score += 35.0
    if min_dim / max(1.0, max_dim) <= 0.08 and planar_ratio >= 0.75:
        score += 30.0
    score += min(20.0, planar_ratio * 20.0)
    if len(features.holes) > 0 or len(features.pockets) > 0:
        score += 5.0
    if profile_count > 8 and bend_count == 0:
        score -= min(35.0, profile_count * 0.4)
    return {
        "bbox_x_mm": float(bbox[0]),
        "bbox_y_mm": float(bbox[1]),
        "bbox_z_mm": float(bbox[2]),
        "max_dimension_mm": float(max_dim),
        "min_dimension_mm": float(min_dim),
        "estimated_thickness_mm": float(estimated_thickness),
        "part_volume_cm3": float(volume / 1000.0),
        "surface_area_cm2": float(surface_area / 100.0),
        "projected_area_cm2": float(projected_area / 100.0),
        "flat_pattern_area_cm2": float(flat_area_cm2),
        "thinness_ratio": float(min_dim / max(1.0, max_dim)),
        "wall_proxy_mm": float(max(0.5, min(8.0, (2.0 * volume) / surface_area))),
        "face_count": float(len(features.faces)),
        "edge_count": float(len(features.edges)),
        "non_planar_face_ratio": float(non_planar_ratio),
        "planar_face_ratio": float(planar_ratio),
        "hole_count": float(len(features.holes)),
        "pocket_count": float(len(features.pockets)),
        "profile_candidate_count": float(profile_count),
        "bend_candidate_count": float(bend_count),
        "estimated_cut_length_mm": float(cut_length_mm),
        "complexity_score": float(features.complexity.score),
        "sheet_metal_confidence_score": float(round(max(0.0, min(100.0, score)), 1)),
    }


def _flat_pattern_area_cm2(volume_mm3: float, thickness_mm: float, projected_area_mm2: float) -> float:
    if volume_mm3 > 0 and thickness_mm > 0:
        return float((volume_mm3 / thickness_mm) / 100.0)
    return float(projected_area_mm2 / 100.0)
