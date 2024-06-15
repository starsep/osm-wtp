import json
import os
from dataclasses import dataclass
from typing import List

import httpx

import logger
from logger import log_duration
from model.types import RouteRef, StopRef

API_UM_WARSZAWA_API_KEY = os.getenv("API_KEY")


@dataclass(frozen=True)
class APIUMWarszawaRouteResult:
    routeRef: RouteRef
    variantId: str
    stopRefs: List[StopRef]


@log_duration
def _parseApiUMData(data) -> dict[RouteRef, List[APIUMWarszawaRouteResult]]:
    result = dict()
    for routeRef in data:
        result[routeRef] = []
        for variantId in data[routeRef]:
            stops = data[routeRef][variantId]
            stopRefs = [
                # ignored fields: odleglosc, ulica_id, typ
                stop["nr_zespolu"] + stop["nr_przystanku"]
                for _, stop in sorted(stops.items(), key=lambda x: int(x[0]))
            ]
            result[routeRef].append(
                APIUMWarszawaRouteResult(
                    routeRef=routeRef,
                    variantId=variantId,
                    stopRefs=stopRefs,
                )
            )
    return result


def fetchApiRoutes() -> dict[RouteRef, List[APIUMWarszawaRouteResult]]:
    if API_UM_WARSZAWA_API_KEY is None:
        logger.error(
            "Missing API UM Warszawa api key. Set it as API_KEY environment variable"
        )
        return dict()
    try:
        resourceId = "26b9ade1-f5d4-439e-84b4-9af37ab7ebf1"
        url = f"https://api.um.warszawa.pl/api/action/public_transport_routes/?apikey={API_UM_WARSZAWA_API_KEY}&resource_id={resourceId}"
        with log_duration("Downloading data from API UM Warszawa"):
            response = httpx.get(url)
            response.raise_for_status()
        with log_duration("Parsing API UM Warszawa JSON"):
            data = json.loads(response.text)["result"]
        return _parseApiUMData(data)
    except Exception as e:
        logger.error(f"Failed to fetch data from API UM Warszawa: {e}")
        return dict()
