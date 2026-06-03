from __future__ import annotations

from app.cad.edge_analysis import analyze_edges
from app.cad.face_analysis import analyze_faces
from app.cad.feature_recognizers import DEFERRED_FEATURE_TYPES, DETECTOR_VERSIONS, recognize_holes, recognize_pockets
from app.cad.step_reader import StepReader, StepShapeContext
from app.cad.topology import build_topology_index
from app.schemas.features import ComplexityScore, FaceAdjacency, FeatureDiagnostics, FeatureExtractionResult


class FeatureExtractor:
    def __init__(self, step_reader: StepReader | None = None) -> None:
        self.step_reader = step_reader or StepReader()

    def extract_from_path(self, path: str) -> FeatureExtractionResult:
        return self.extract_from_context(self.step_reader.load_context(path))

    def extract_from_context(self, context: StepShapeContext) -> FeatureExtractionResult:
        topology = build_topology_index(context.shape)
        faces = analyze_faces(topology)
        edges = analyze_edges(topology)
        adjacency = self._build_adjacency(edges, {face.face_id: face.surface_type for face in faces})
        holes, hole_warnings, rejected_candidates = recognize_holes(faces, edges)
        pockets, pocket_warnings = recognize_pockets(faces, adjacency)
        warnings = sorted(set([*hole_warnings, *pocket_warnings]))

        return FeatureExtractionResult(
            schema_version="1.0",
            source=context.parse_result,
            faces=faces,
            edges=edges,
            adjacency=adjacency,
            holes=holes,
            pockets=pockets,
            complexity=self._complexity(faces, edges, holes, pockets, warnings),
            diagnostics=FeatureDiagnostics(
                detector_versions=DETECTOR_VERSIONS,
                warnings=warnings,
                deferred_feature_types=DEFERRED_FEATURE_TYPES,
                rejected_candidates=rejected_candidates,
            ),
        )

    def _build_adjacency(self, edges: list, face_surface_types: dict[str, str]) -> list[FaceAdjacency]:
        adjacency: list[FaceAdjacency] = []
        for edge in edges:
            classification = "boundary"
            if len(edge.adjacent_face_ids) == 2:
                left_type = face_surface_types.get(edge.adjacent_face_ids[0], "unknown")
                right_type = face_surface_types.get(edge.adjacent_face_ids[1], "unknown")
                if left_type == right_type == "plane":
                    classification = "sharp_planar"
                elif "cylinder" in {left_type, right_type}:
                    classification = "cylindrical_boundary"
                else:
                    classification = "adjacent"
            adjacency.append(
                FaceAdjacency(
                    edge_id=edge.edge_id,
                    face_ids=edge.adjacent_face_ids,
                    classification=classification,
                )
            )
        return adjacency

    def _complexity(self, faces: list, edges: list, holes: list, pockets: list, warnings: list[str]) -> ComplexityScore:
        non_planar_faces = sum(1 for face in faces if face.surface_type != "plane")
        non_planar_ratio = non_planar_faces / max(1, len(faces))
        raw_score = (
            len(faces) * 0.6
            + len(edges) * 0.15
            + non_planar_ratio * 25.0
            + len(holes) * 4.0
            + len(pockets) * 6.0
            + len(warnings) * 3.0
        )
        score = int(max(0, min(100, round(raw_score))))
        return ComplexityScore(
            score=score,
            signals={
                "face_count": float(len(faces)),
                "edge_count": float(len(edges)),
                "non_planar_face_ratio": float(non_planar_ratio),
                "hole_count": float(len(holes)),
                "pocket_count": float(len(pockets)),
                "warning_count": float(len(warnings)),
            },
        )
