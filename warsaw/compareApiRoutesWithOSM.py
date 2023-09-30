import logger
from model.types import RouteRef
from osm.OSMRelationAnalyzer import VariantResult
from warsaw.fetchApiRoutes import fetchApiRoutes


def compareApiRoutesWithOSM(osmResults: dict[RouteRef, list[VariantResult]]):
    apiResults = fetchApiRoutes()
    for routeRef, variants in osmResults.items():
        if routeRef not in apiResults:
            logger.warn(f"Missing {routeRef} in API UM results")
            continue
        for variant in variants:
            variantStopRefs = [stop.ref for stop in variant.osmStops]
            match = None
            for apiResult in apiResults[routeRef]:
                if apiResult.stopRefs == variantStopRefs:
                    match = apiResult
                    break
            if match is None:
                logger.warn(
                    f"Couldn't find match for {variant.osmName} ({variant.osmId})"
                )
            else:
                logger.info(
                    f"Match for {variant.osmName} ({variant.osmId}) ===> {match.routeRef} {match.variantId}"
                )
