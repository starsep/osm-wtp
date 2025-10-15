from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import zip_longest

from configuration import MISSING_REF
from model.types import RouteRef, StopName, StopRef
from osm.OSMRelationAnalyzer import OSMResults, VariantResult, osmRefToName


@dataclass(frozen=True)
class DiffRow:
    color: str
    refOSM: StopRef
    nameOSM: StopName
    refOperator: StopRef
    nameOperator: StopName
    detour: bool
    new: bool


@dataclass(frozen=True)
class RenderVariantResult:
    variant: VariantResult
    diffRows: list[DiffRow]
    otherErrors: list[str]


@dataclass(frozen=True)
class RouteResult:
    routeMismatch: bool
    error: bool
    detourOnlyErrors: bool
    variantResults: list[RenderVariantResult]


@dataclass(frozen=True)
class CompareResult:
    renderResults: dict[RouteRef, RouteResult]
    refs: list[RouteRef]
    operatorRefToName: dict[StopRef, set[StopName]]


def compareStops(osmResults: OSMResults) -> CompareResult:
    renderResults: dict[RouteRef, RouteResult] = {}
    refs = sorted(osmResults.keys(), key=lambda x: (len(x), x))
    operatorRefToName: dict[StopRef, set[StopName]] = {}
    for routeRef in refs:
        detourOnlyErrors = True
        variantResults = []
        routeMismatch = False
        error = False
        for variant in osmResults[routeRef]:
            osmRefs: list[StopRef] = [stop.ref for stop in variant.osmStops]
            operatorRefs: list[StopRef] = [stop.ref for stop in variant.operatorStops]
            for stop in variant.operatorStops:
                if stop.ref not in operatorRefToName:
                    operatorRefToName[stop.ref] = set()
                operatorRefToName[stop.ref].add(stop.name)
            otherErrors = variant.otherErrors
            if len(variant.unknownRoles) > 0:
                otherErrors.add(f"Nieznane role: {variant.unknownRoles}")
            diffRows = buildDiffRows(
                osmRefs,
                operatorRefs,
                operatorRefToName,
                variant.stopsDetour,
                variant.stopsNew,
            )
            if osmRefs != operatorRefs and (not variant.detour):
                detourOnlyErrors = False
            error |= len(otherErrors) > 0 or len(diffRows) > 0
            if error:
                variantResults.append(
                    RenderVariantResult(
                        variant=variant,
                        diffRows=diffRows,
                        otherErrors=sorted(otherErrors),
                    ),
                )
            routeMismatch |= osmRefs != operatorRefs
            renderResults[routeRef] = RouteResult(
                routeMismatch=routeMismatch,
                error=error,
                detourOnlyErrors=detourOnlyErrors,
                variantResults=variantResults,
            )
    return CompareResult(
        renderResults=renderResults,
        refs=refs,
        operatorRefToName=operatorRefToName,
    )


def buildDiffRows(
    osmRefs: list[StopRef],
    operatorRefs: list[StopRef],
    operatorRefToName: dict[StopRef, set[StopName]],
    stopsDetour: list[bool],
    stopsNew: list[bool],
) -> list[DiffRow]:
    diffRows = []
    if osmRefs == operatorRefs:
        return diffRows
    matcher = SequenceMatcher(None, osmRefs, operatorRefs)
    detourRefs = {
        ref for ref, detour in zip(operatorRefs, stopsDetour, strict=False) if detour
    }
    newRefs = {ref for ref, new in zip(operatorRefs, stopsNew, strict=False) if new}

    def writeTableRow(refOSM: StopRef, refOperator: StopRef) -> None:
        nameOSM = (
            next(iter(osmRefToName[refOSM])) if refOSM != MISSING_REF else MISSING_REF
        )
        nameOperator = (
            next(iter(operatorRefToName[refOperator]))
            if refOperator != MISSING_REF
            else MISSING_REF
        )
        color = "inherit"
        if refOSM == refOperator:
            color = "inherit"
        elif refOSM == MISSING_REF:
            color = "green"
        elif MISSING_REF not in (refOSM, refOperator):
            color = "orange"
        elif refOperator == MISSING_REF and nameOperator == MISSING_REF:
            color = "red"
        elif refOperator == MISSING_REF and nameOperator != MISSING_REF:
            color = "orange" if nameOSM != nameOperator else "inherit"
        diffRows.append(
            DiffRow(
                color=color,
                refOSM=refOSM,
                nameOSM=nameOSM,
                refOperator=refOperator,
                nameOperator=nameOperator,
                detour=refOperator in detourRefs,
                new=refOperator in newRefs,
            ),
        )

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2), strict=False):
                writeTableRow(refOSM=osmRefs[i], refOperator=operatorRefs[j])
        elif tag == "delete":
            for i in range(i1, i2):
                writeTableRow(refOSM=osmRefs[i], refOperator=MISSING_REF)
        elif tag == "insert":
            for j in range(j1, j2):
                writeTableRow(refOSM=MISSING_REF, refOperator=operatorRefs[j])
        elif tag == "replace":
            for i, j in zip_longest(range(i1, i2), range(j1, j2), fillvalue=None):
                writeTableRow(
                    refOSM=osmRefs[i] if i is not None else MISSING_REF,
                    refOperator=operatorRefs[j] if j is not None else MISSING_REF,
                )
    return diffRows
