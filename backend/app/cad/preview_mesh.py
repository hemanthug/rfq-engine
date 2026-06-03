from __future__ import annotations

import math
from typing import Any

from app.cad.errors import PreviewMeshError, PreviewMeshTooLargeError
from app.config import Settings, get_settings
from app.schemas.cad import BoundingBox
from app.schemas.preview import PreviewMeshQuality, PreviewMeshResult


def _import_occ_modules() -> dict[str, Any]:
    from OCC.Core import BRep, TopAbs, TopExp, TopoDS
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopLoc import TopLoc_Location

    return {
        "BRep": BRep,
        "BRepMesh_IncrementalMesh": BRepMesh_IncrementalMesh,
        "TopAbs": TopAbs,
        "TopExp": TopExp,
        "TopoDS": TopoDS,
        "TopLoc_Location": TopLoc_Location,
    }


class PreviewMeshBuilder:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def build(self, shape: Any, bbox: BoundingBox) -> PreviewMeshResult:
        modules = _import_occ_modules()
        linear_deflection = self.settings.preview_linear_deflection_mm
        angular_deflection = self.settings.preview_angular_deflection_rad
        is_relative = False
        is_parallel = True

        mesh = modules["BRepMesh_IncrementalMesh"](
            shape,
            linear_deflection,
            is_relative,
            angular_deflection,
            is_parallel,
        )
        if hasattr(mesh, "IsDone") and not mesh.IsDone():
            raise PreviewMeshError("OpenCascade tessellation did not complete.")

        positions: list[float] = []
        normals: list[float] = []
        indices: list[int] = []
        edges: list[float] = []
        warnings: list[str] = []
        triangle_count = 0
        face_count_without_triangulation = 0

        explorer = modules["TopExp"].TopExp_Explorer(shape, modules["TopAbs"].TopAbs_FACE)
        while explorer.More():
            face = modules["TopoDS"].topods.Face(explorer.Current())
            location = modules["TopLoc_Location"]()
            triangulation = modules["BRep"].BRep_Tool.Triangulation(face, location)
            if triangulation is None or int(triangulation.NbTriangles()) <= 0:
                face_count_without_triangulation += 1
                explorer.Next()
                continue

            transformation = location.Transformation()
            reversed_face = int(face.Orientation()) == int(modules["TopAbs"].TopAbs_REVERSED)
            for triangle_index in range(1, int(triangulation.NbTriangles()) + 1):
                if triangle_count + 1 > self.settings.preview_max_triangles:
                    raise PreviewMeshTooLargeError(
                        "Preview mesh exceeds the configured triangle limit.",
                        triangle_count=triangle_count + 1,
                        max_triangles=self.settings.preview_max_triangles,
                    )

                node_ids = list(triangulation.Triangle(triangle_index).Get())
                if reversed_face:
                    node_ids[1], node_ids[2] = node_ids[2], node_ids[1]
                points = [triangulation.Node(node_id).Transformed(transformation) for node_id in node_ids]
                normal = _triangle_normal(points)
                base_index = len(positions) // 3
                for point in points:
                    positions.extend([float(point.X()), float(point.Y()), float(point.Z())])
                    normals.extend(normal)
                indices.extend([base_index, base_index + 1, base_index + 2])
                _append_triangle_edges(edges, points)
                triangle_count += 1

            explorer.Next()

        if triangle_count <= 0:
            raise PreviewMeshError("OpenCascade produced no preview triangles.")
        if face_count_without_triangulation:
            warnings.append("some_faces_missing_triangulation")

        vertex_count = len(positions) // 3
        return PreviewMeshResult(
            schema_version="1.0",
            units="MM",
            positions=positions,
            normals=normals,
            indices=indices,
            edges=edges,
            bbox=bbox,
            triangle_count=triangle_count,
            vertex_count=vertex_count,
            mesh_quality=PreviewMeshQuality(
                linear_deflection_mm=linear_deflection,
                angular_deflection_rad=angular_deflection,
                is_relative=is_relative,
                is_parallel=is_parallel,
                warnings=warnings,
            ),
        )


def _triangle_normal(points: list[Any]) -> list[float]:
    ax, ay, az = float(points[0].X()), float(points[0].Y()), float(points[0].Z())
    bx, by, bz = float(points[1].X()), float(points[1].Y()), float(points[1].Z())
    cx, cy, cz = float(points[2].X()), float(points[2].Y()), float(points[2].Z())
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 0:
        return [0.0, 0.0, 1.0]
    return [nx / length, ny / length, nz / length]


def _append_triangle_edges(edges: list[float], points: list[Any]) -> None:
    for start, end in ((0, 1), (1, 2), (2, 0)):
        for point in (points[start], points[end]):
            edges.extend([float(point.X()), float(point.Y()), float(point.Z())])
