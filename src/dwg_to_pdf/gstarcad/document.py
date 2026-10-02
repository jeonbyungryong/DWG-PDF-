from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Iterable
import uuid

import pythoncom
from win32com.client import VARIANT

from ..domain import Rect
from ..errors import AppError
from ..templates.scale_label import parse_internal_scale

AC_SELECTION_SET_CROSSING = 1
AC_SELECTION_SET_ALL = 5
_SUPPORTED_FILTER_TYPES = frozenset({"TEXT", "MTEXT", "INSERT", "LINE", "LWPOLYLINE"})
_ANNOTATION_ONLY_OBJECT_NAMES = frozenset({"ACDBPOINT"})
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass
class TraversalBudget:
    max_roots: int
    max_blocks: int
    max_entities: int
    roots: int = 0
    blocks: int = 0
    entities: int = 0

    def _visit(self, field: str, maximum: int, label: str) -> None:
        value = getattr(self, field) + 1
        setattr(self, field, value)
        if value > maximum:
            raise AppError("E303", f"nested traversal exceeded aggregate {label} limit")

    def visit_root(self) -> None:
        self._visit("roots", self.max_roots, "root INSERT")

    def visit_block(self) -> None:
        self._visit("blocks", self.max_blocks, "block")

    def visit_entity(self) -> None:
        self._visit("entities", self.max_entities, "entity")


def _finite_number(value: object, description: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise AppError("E303", f"invalid {description}") from exc
    if not math.isfinite(number):
        raise AppError("E303", f"non-finite {description}")
    return number


def _point(entity: Any) -> tuple[float, float]:
    raw = getattr(entity, "InsertionPoint", None)
    if raw is None:
        raw = getattr(entity, "StartPoint", None)
    if raw is None:
        raw = getattr(entity, "Coordinates", None)
    try:
        values = tuple(raw)
        if len(values) < 2:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise AppError("E303", "could not snapshot entity point") from exc
    return _finite_number(values[0], "entity x coordinate"), _finite_number(values[1], "entity y coordinate")


def _entity_type(entity: Any) -> str:
    try:
        object_name = str(entity.ObjectName).upper()
    except Exception as exc:
        raise AppError("E303", "could not snapshot entity type") from exc
    if "BLOCKREFERENCE" in object_name:
        return "INSERT"
    if "MTEXT" in object_name:
        return "MTEXT"
    if "ATTRIBUTE" in object_name:
        return "ATTRIB"
    if "TEXT" in object_name:
        return "TEXT"
    if "POLYLINE" in object_name:
        return "LWPOLYLINE"
    if object_name.endswith("LINE"):
        return "LINE"
    raise AppError("E303", f"unsupported filtered entity type: {object_name}")


def _is_permitted_annotation_only_entity(entity: Any) -> bool:
    """Return true only for block entities proven irrelevant to current detection."""

    try:
        return str(entity.ObjectName).upper() in _ANNOTATION_ONLY_OBJECT_NAMES
    except Exception as exc:
        raise AppError("E303", "could not snapshot entity type") from exc


def _snapshot(entity: Any) -> dict[str, object]:
    kind = _entity_type(entity)
    try:
        result: dict[str, object] = {
            "type": kind,
            "text": str(getattr(entity, "TextString", "")),
            "point": _point(entity),
            "handle": str(entity.Handle),
        }
        if kind in {"TEXT", "MTEXT", "ATTRIB"} and hasattr(entity, "GetBoundingBox"):
            lower, upper = entity.GetBoundingBox()
            result["bbox"] = (
                (_finite_number(lower[0], "text bbox lower x"), _finite_number(lower[1], "text bbox lower y")),
                (_finite_number(upper[0], "text bbox upper x"), _finite_number(upper[1], "text bbox upper y")),
            )
        if kind == "INSERT":
            # Name addresses the actual Blocks.Item definition. EffectiveName can
            # be a user-facing dynamic block name and is not safe for *U blocks.
            result.update(
                block_name=str(entity.Name),
                effective_name=str(getattr(entity, "EffectiveName", entity.Name)),
                rotation=_finite_number(getattr(entity, "Rotation", 0.0), "block rotation"),
                x_scale=_finite_number(getattr(entity, "XScaleFactor", 1.0), "block x scale"),
                y_scale=_finite_number(getattr(entity, "YScaleFactor", 1.0), "block y scale"),
                has_attributes=bool(getattr(entity, "HasAttributes", False)),
            )
        elif kind == "LINE":
            result["start"] = (
                _finite_number(entity.StartPoint[0], "line start x"),
                _finite_number(entity.StartPoint[1], "line start y"),
            )
            result["end"] = (
                _finite_number(entity.EndPoint[0], "line end x"),
                _finite_number(entity.EndPoint[1], "line end y"),
            )
        elif kind == "LWPOLYLINE":
            coordinates = tuple(entity.Coordinates)
            if len(coordinates) < 4 or len(coordinates) % 2:
                raise AppError("E303", "invalid polyline coordinates")
            result["coordinates"] = tuple(
                _finite_number(value, "polyline coordinate") for value in coordinates
            )
            result["closed"] = bool(getattr(entity, "Closed", False))
            try:
                elevation_raw = entity.Elevation
                normal_raw = tuple(entity.Normal)
            except Exception as exc:
                raise AppError("E303", "polyline planarity properties are unavailable") from exc
            elevation = _finite_number(elevation_raw, "polyline elevation")
            normal = tuple(
                _finite_number(value, "polyline normal component") for value in normal_raw
            )
            if (
                not math.isclose(elevation, 0.0, abs_tol=1e-12)
                or len(normal) < 3
                or not all(math.isclose(value, expected, abs_tol=1e-12) for value, expected in zip(normal[:3], (0.0, 0.0, 1.0)))
            ):
                raise AppError("E303", "unsupported elevated or non-planar polyline")
            segment_count = len(coordinates) // 2 if result["closed"] else len(coordinates) // 2 - 1
            for index in range(segment_count):
                bulge = _finite_number(entity.GetBulge(index), "polyline bulge")
                if not math.isclose(bulge, 0.0, abs_tol=1e-12):
                    raise AppError("E303", "unsupported curved polyline bulge")
        return result
    except AppError:
        raise
    except Exception as exc:
        raise AppError("E303", "could not snapshot filtered entity") from exc


def _matrix_for(reference: dict[str, object]) -> tuple[float, float, float, float, float, float]:
    angle = _finite_number(reference.get("rotation", 0.0), "block transform rotation")
    sx = _finite_number(reference.get("x_scale", 1.0), "block transform x scale")
    sy = _finite_number(reference.get("y_scale", 1.0), "block transform y scale")
    x, y = reference.get("point", (None, None))
    tx = _finite_number(x, "block transform x translation")
    ty = _finite_number(y, "block transform y translation")
    if not (
        math.isclose(sx, 1.0, rel_tol=1e-9, abs_tol=1e-12)
        and math.isclose(sy, 1.0, rel_tol=1e-9, abs_tol=1e-12)
    ):
        raise AppError("E303", "unsupported scaled or reflected block transform")
    quarter_turn = math.pi / 2
    nearest_quarter = round(angle / quarter_turn)
    if not math.isclose(angle, nearest_quarter * quarter_turn, rel_tol=0.0, abs_tol=1e-9):
        raise AppError("E303", "unsupported non-quarter-turn block transform")
    cosine, sine = math.cos(angle), math.sin(angle)
    matrix = (cosine * sx, -sine * sy, sine * sx, cosine * sy, tx, ty)
    _require_similarity(matrix)
    return matrix


def _has_unsupported_root_transform(reference: dict[str, object]) -> bool:
    try:
        _matrix_for(reference)
    except AppError as exc:
        return str(exc) in {
            "unsupported scaled or reflected block transform",
            "unsupported non-quarter-turn block transform",
        }
    return False


def _require_similarity(matrix: tuple[float, ...]) -> None:
    if len(matrix) != 6 or not all(math.isfinite(value) for value in matrix):
        raise AppError("E303", "non-finite block transform")
    a, b, c, d, _, _ = matrix
    first_norm = a * a + c * c
    second_norm = b * b + d * d
    dot = a * b + c * d
    determinant = a * d - b * c
    scale = max(first_norm, second_norm, 1.0)
    if determinant <= 0 or not math.isclose(first_norm, second_norm, rel_tol=1e-9, abs_tol=1e-12):
        raise AppError("E303", "unsupported non-uniform block transform")
    if not math.isclose(dot, 0.0, abs_tol=1e-10 * scale):
        raise AppError("E303", "unsupported sheared block transform")


def _compose(parent: tuple[float, ...], child: tuple[float, ...]) -> tuple[float, ...]:
    pa, pb, pc, pd, ptx, pty = parent
    ca, cb, cc, cd, ctx, cty = child
    result = (
        pa * ca + pb * cc,
        pa * cb + pb * cd,
        pc * ca + pd * cc,
        pc * cb + pd * cd,
        pa * ctx + pb * cty + ptx,
        pc * ctx + pd * cty + pty,
    )
    _require_similarity(result)
    return result


def _apply(matrix: tuple[float, ...], point: tuple[float, float]) -> tuple[float, float]:
    a, b, c, d, tx, ty = matrix
    result = (a * point[0] + b * point[1] + tx, c * point[0] + d * point[1] + ty)
    if not all(math.isfinite(value) for value in result):
        raise AppError("E303", "non-finite transformed entity geometry")
    return result


def _apply_bbox(matrix: tuple[float, ...], bbox: object) -> tuple[tuple[float, float], tuple[float, float]]:
    lower, upper = bbox
    corners = (
        _apply(matrix, (lower[0], lower[1])), _apply(matrix, (lower[0], upper[1])),
        _apply(matrix, (upper[0], lower[1])), _apply(matrix, (upper[0], upper[1])),
    )
    return (
        (min(point[0] for point in corners), min(point[1] for point in corners)),
        (max(point[0] for point in corners), max(point[1] for point in corners)),
    )


def _collection_count(collection: Any, description: str) -> int:
    try:
        count = int(collection.Count)
    except Exception as exc:
        raise AppError("E303", f"could not read {description} count") from exc
    if count < 0:
        raise AppError("E303", f"invalid {description} count")
    return count


def _attribute_snapshots(reference: Any) -> list[dict[str, object]]:
    try:
        if not bool(getattr(reference, "HasAttributes", False)):
            return []
        attributes: Iterable[Any] = reference.GetAttributes()
        return [_snapshot(attribute) for attribute in attributes]
    except AppError:
        raise
    except Exception as exc:
        raise AppError("E303", "could not snapshot block attributes") from exc


@dataclass
class GstarDocument:
    raw: Any
    _geometry_cache: dict[
        tuple[Rect, int, int], tuple[dict[str, object], ...]
    ] = field(default_factory=dict, init=False, repr=False)

    def approved_reference_window(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Read the saved Plot Window; callers must restrict this to approved references."""

        try:
            lower, upper = self.raw.ActiveLayout.GetWindowToPlot()
            result = (
                (_finite_number(lower[0], "reference Window lower x"), _finite_number(lower[1], "reference Window lower y")),
                (_finite_number(upper[0], "reference Window upper x"), _finite_number(upper[1], "reference Window upper y")),
            )
        except AppError:
            raise
        except Exception as exc:
            raise AppError("E306", "approved reference Plot Window could not be read") from exc
        if result[0][0] >= result[1][0] or result[0][1] >= result[1][1]:
            raise AppError("E306", "approved reference Plot Window is inverted")
        return result

    def filtered_snapshots(
        self,
        types: tuple[str, ...],
        bounds: Rect | None = None,
    ) -> list[dict[str, object]]:
        normalized = tuple(str(kind).strip().upper() for kind in types)
        if not normalized or len(set(normalized)) != len(normalized):
            raise ValueError("filtered entity types must be non-empty and unique")
        unsupported = set(normalized) - _SUPPORTED_FILTER_TYPES
        if unsupported:
            raise ValueError(f"unsupported filtered entity types: {sorted(unsupported)}")
        name = f"DWG_TO_PDF_FILTERED_{uuid.uuid4().hex}"
        try:
            self.raw.SelectionSets.Item(name).Delete()
        except Exception:
            pass
        try:
            selection = self.raw.SelectionSets.Add(name)
        except Exception as exc:
            raise AppError("E303", "could not create filtered selection set") from exc

        filter_types = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, (0,))
        filter_data = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, (",".join(normalized),))
        pending_error: BaseException | None = None
        try:
            if bounds is None:
                # GstarCAD rejects VT_NULL, while VT_ERROR/Missing causes the
                # trailing filters to be ignored. VT_EMPTY preserves them.
                selection.Select(
                    AC_SELECTION_SET_ALL,
                    pythoncom.Empty,
                    pythoncom.Empty,
                    filter_types,
                    filter_data,
                )
            else:
                coordinates = (
                    bounds.lower_left.x,
                    bounds.lower_left.y,
                    bounds.upper_right.x,
                    bounds.upper_right.y,
                )
                if not all(math.isfinite(value) for value in coordinates):
                    raise AppError("E303", "non-finite filtered selection bounds")
                point1 = VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_R8,
                    (bounds.lower_left.x, bounds.lower_left.y, 0.0),
                )
                point2 = VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_R8,
                    (bounds.upper_right.x, bounds.upper_right.y, 0.0),
                )
                selection.Select(
                    AC_SELECTION_SET_CROSSING,
                    point1,
                    point2,
                    filter_types,
                    filter_data,
                )
            snapshots: list[dict[str, object]] = []
            for index in range(_collection_count(selection, "selection")):
                entity = selection.Item(index)
                snapshot = _snapshot(entity)
                snapshots.append(snapshot)
                if snapshot["type"] == "INSERT":
                    snapshots.extend(_attribute_snapshots(entity))
            return snapshots
        except AppError as exc:
            pending_error = exc
            raise
        except Exception as exc:
            error = AppError("E303", "filtered GstarCAD selection failed")
            pending_error = error
            raise error from exc
        finally:
            try:
                selection.Delete()
            except Exception as exc:
                if pending_error is None:
                    raise AppError("E303", "could not delete filtered selection set") from exc

    def nested_text_snapshots(
        self,
        reference: dict[str, object],
        max_blocks: int | None = None,
        max_entities: int | None = None,
        *,
        budget: TraversalBudget | None = None,
    ) -> list[dict[str, object]]:
        if budget is None:
            if max_blocks is None or max_entities is None or max_blocks <= 0 or max_entities <= 0:
                raise ValueError("nested traversal limits must be positive")
            budget = TraversalBudget(1, max_blocks, max_entities)
            budget.visit_root()
        root_name = str(reference.get("block_name", ""))
        if not root_name:
            raise AppError("E303", "filtered INSERT has no block definition name")
        root_path = (str(reference.get("handle", "<root>")),)
        stack = [(
            root_name,
            _matrix_for(reference),
            frozenset(),
            bool(reference.get("has_attributes", False)),
            root_path,
        )]
        output: list[dict[str, object]] = []

        while stack:
            name, matrix, ancestry, suppress_attribute_definitions, instance_path = stack.pop()
            if name in ancestry:
                continue
            budget.visit_block()
            try:
                block = self.raw.Blocks.Item(name)
            except Exception as exc:
                raise AppError("E303", f"could not access reached block definition: {name}") from exc
            child_ancestry = ancestry | {name}
            for index in range(_collection_count(block, f"block {name}")):
                budget.visit_entity()
                try:
                    entity = block.Item(index)
                    kind = _entity_type(entity)
                except AppError as exc:
                    if "unsupported filtered entity type" in str(exc):
                        continue
                    raise
                local = _snapshot(entity)
                if kind == "ATTRIB" and suppress_attribute_definitions:
                    continue
                if kind == "INSERT":
                    for attribute in _attribute_snapshots(entity):
                        budget.visit_entity()
                        attribute["point"] = _apply(matrix, attribute["point"])
                        if "bbox" in attribute:
                            attribute["bbox"] = _apply_bbox(matrix, attribute["bbox"])
                        attribute["instance_path"] = instance_path + (str(local.get("handle", "")),)
                        output.append(attribute)
                    child_name = str(local.get("block_name", ""))
                    if child_name and child_name not in child_ancestry:
                        stack.append((
                            child_name,
                            _compose(matrix, _matrix_for(local)),
                            child_ancestry,
                            bool(local.get("has_attributes", False)),
                            instance_path + (str(local.get("handle", "")),),
                        ))
                else:
                    local["point"] = _apply(matrix, local["point"])
                    if "bbox" in local:
                        local["bbox"] = _apply_bbox(matrix, local["bbox"])
                    local["instance_path"] = instance_path
                    output.append(local)
        return output

    def is_noncontributing_unsupported_insert(
        self,
        reference: dict[str, object],
        *,
        budget: TraversalBudget,
    ) -> bool:
        """Ignore unsupported INSERT geometry so it cannot create a false match.

        Dropping geometry can only reduce a registered signature score.  A
        title/frame held exclusively inside an unsupported transform therefore
        remains below threshold instead of being interpreted approximately.
        """

        return _has_unsupported_root_transform(reference)

    def is_known_noncontributing_text_insert(self, reference: dict[str, object]) -> bool:
        """Recognize unattributed SolidWorks center-mark geometry by its native name."""

        if bool(reference.get("has_attributes", False)):
            return False
        names = (
            str(reference.get("block_name", "")).upper(),
            str(reference.get("effective_name", "")).upper(),
        )
        return any(name.startswith("SW_CENTERMARKSYMBOL_") for name in names)

    def is_noncontributing_text_insert(
        self,
        reference: dict[str, object],
        *,
        budget: TraversalBudget,
    ) -> bool:
        """Return whether a reached block definition cannot affect Scale detection."""

        root_name = str(reference.get("block_name", ""))
        if not root_name:
            raise AppError("E303", "filtered INSERT has no block definition name")
        stack = [(root_name, frozenset())]
        while stack:
            name, ancestry = stack.pop()
            if name in ancestry:
                continue
            budget.visit_block()
            try:
                block = self.raw.Blocks.Item(name)
            except Exception as exc:
                raise AppError("E303", f"could not access reached block definition: {name}") from exc
            child_ancestry = ancestry | {name}
            for index in range(_collection_count(block, f"block {name}")):
                budget.visit_entity()
                entity = block.Item(index)
                try:
                    kind = _entity_type(entity)
                except AppError as exc:
                    if (
                        "unsupported filtered entity type" in str(exc)
                        or _is_permitted_annotation_only_entity(entity)
                    ):
                        continue
                    raise
                if kind in {"TEXT", "MTEXT", "ATTRIB"}:
                    text = str(getattr(entity, "TextString", "")).strip()
                    if text.casefold() in {"scale", "n/a"}:
                        return False
                    try:
                        parse_internal_scale(text)
                    except AppError:
                        if kind == "ATTRIB" and not text:
                            # A blank attribute definition can receive the Scale
                            # value at the block-reference instance level.
                            return False
                        continue
                    return False
                if kind in {"LINE", "LWPOLYLINE"}:
                    continue
                local = _snapshot(entity)
                if kind == "INSERT":
                    if bool(local.get("has_attributes", False)):
                        return False
                    child_name = str(local.get("block_name", ""))
                    if child_name and child_name not in child_ancestry:
                        stack.append((child_name, child_ancestry))
        return True

    def filtered_geometry_snapshots(
        self, bounds: Rect, max_blocks: int = 64, max_entities: int = 5000
    ) -> list[dict[str, object]]:
        """Return finite primitive segments from one server-bounded selection."""

        cache_key = (bounds, max_blocks, max_entities)
        cached = self._geometry_cache.get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]

        snapshots = self.filtered_snapshots(("LINE", "LWPOLYLINE", "INSERT"), bounds)
        references = [item for item in snapshots if item["type"] == "INSERT"]
        budget = TraversalBudget(max_blocks, max_blocks, max_entities)
        for reference in references:
            if self.is_known_noncontributing_text_insert(reference):
                continue
            if self.is_noncontributing_unsupported_insert(reference, budget=budget):
                continue
            budget.visit_root()
            snapshots.extend(self.nested_geometry_snapshots(reference, budget=budget))
        output: list[dict[str, object]] = []
        for item in snapshots:
            if item["type"] == "INSERT":
                continue
            if item["type"] == "LINE":
                line = {
                    "type": "LINE", "start": item["start"], "end": item["end"],
                    "handle": item["handle"],
                }
                if "instance_path" in item:
                    line["instance_path"] = item["instance_path"]
                output.append(line)
                continue
            coordinates = item["coordinates"]
            vertices = [(coordinates[index], coordinates[index + 1]) for index in range(0, len(coordinates), 2)]
            pairs = list(zip(vertices, vertices[1:]))
            if item.get("closed"):
                pairs.append((vertices[-1], vertices[0]))
            for index, (start, end) in enumerate(pairs):
                line = {
                    "type": "LINE", "start": start, "end": end,
                    "handle": f'{item["handle"]}:{index}',
                }
                if "instance_path" in item:
                    line["instance_path"] = item["instance_path"]
                output.append(line)
        self._geometry_cache[cache_key] = tuple(dict(item) for item in output)
        return [dict(item) for item in output]

    def nested_geometry_snapshots(
        self,
        reference: dict[str, object],
        max_blocks: int | None = None,
        max_entities: int | None = None,
        *,
        budget: TraversalBudget | None = None,
    ) -> list[dict[str, object]]:
        """Traverse only block definitions reached by a server-filtered INSERT."""

        if budget is None:
            if max_blocks is None or max_entities is None or max_blocks <= 0 or max_entities <= 0:
                raise ValueError("nested traversal limits must be positive")
            budget = TraversalBudget(1, max_blocks, max_entities)
            budget.visit_root()
        root_name = str(reference.get("block_name", ""))
        if not root_name:
            raise AppError("E303", "filtered INSERT has no block definition name")
        root_path = (str(reference.get("handle", "<root>")),)
        stack = [(root_name, _matrix_for(reference), frozenset(), root_path)]
        output: list[dict[str, object]] = []
        while stack:
            name, matrix, ancestry, instance_path = stack.pop()
            if name in ancestry:
                continue
            budget.visit_block()
            try:
                block = self.raw.Blocks.Item(name)
            except Exception as exc:
                raise AppError("E303", f"could not access reached block definition: {name}") from exc
            child_ancestry = ancestry | {name}
            for index in range(_collection_count(block, f"block {name}")):
                budget.visit_entity()
                entity = block.Item(index)
                try:
                    kind = _entity_type(entity)
                except AppError as exc:
                    if "unsupported filtered entity type" in str(exc):
                        continue
                    raise
                local = _snapshot(entity)
                if kind == "INSERT":
                    child_name = str(local.get("block_name", ""))
                    if child_name and child_name not in child_ancestry:
                        stack.append((
                            child_name, _compose(matrix, _matrix_for(local)), child_ancestry,
                            instance_path + (str(local.get("handle", "")),),
                        ))
                elif kind == "LINE":
                    output.append({
                        "type": "LINE", "start": _apply(matrix, local["start"]),
                        "end": _apply(matrix, local["end"]), "handle": local["handle"],
                        "instance_path": instance_path,
                    })
                elif kind == "LWPOLYLINE":
                    coordinates = local["coordinates"]
                    transformed = []
                    for offset in range(0, len(coordinates), 2):
                        transformed.extend(_apply(matrix, (coordinates[offset], coordinates[offset + 1])))
                    output.append({
                        "type": "LWPOLYLINE", "coordinates": tuple(transformed),
                        "closed": local["closed"], "handle": local["handle"],
                        "instance_path": instance_path,
                    })
        return output
