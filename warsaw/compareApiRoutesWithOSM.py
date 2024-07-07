import logging
from typing import List

from model.types import RouteRef
from osm.OSMRelationAnalyzer import VariantResult
from warsaw.fetchApiRoutes import APIUMWarszawaRouteResult


# http://localhost:8111/load_object?objects=r16280027&addtags=gtfs:shape_id:like=RA%25/10/TP-WYS
def compareApiRoutesWithOSM(
    apiResults: dict[RouteRef, List[APIUMWarszawaRouteResult]],
    osmResults: dict[RouteRef, List[VariantResult]],
):
    for routeRef, variants in osmResults.items():
        if routeRef not in apiResults:
            logging.warning(f"Missing {routeRef} in API UM results")
            continue
        for variant in variants:
            variantStopRefs = [stop.ref for stop in variant.osmStops]
            match = None
            for apiResult in apiResults[routeRef]:
                if apiResult.stopRefs == variantStopRefs:
                    match = apiResult
                    break
            if match is None:
                logging.warning(
                    f"Couldn't find match for {variant.osmName} ({variant.osmId})"
                )
            else:
                logging.info(
                    f"Match for {variant.osmName} ({variant.osmId}) ===> {match.routeRef} {match.variantId}"
                )
                print(
                    f"http://localhost:8111/load_object?objects=r{variant.osmId}&addtags=gtfs:shape_id:like=RA%25/{match.routeRef}/{match.variantId}"
                )
