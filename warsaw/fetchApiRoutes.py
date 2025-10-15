import json
import logging
import os
from dataclasses import dataclass

import httpx
from starsep_utils import logDuration

from model.types import RouteRef, StopRef

API_UM_WARSZAWA_API_KEY = os.getenv("API_KEY")


@dataclass(frozen=True)
class APIUMWarszawaRouteResult:
    routeRef: RouteRef
    variantId: str
    stopRefs: list[StopRef]


@logDuration
def _parseApiUMData(data: dict) -> dict[RouteRef, list[APIUMWarszawaRouteResult]]:
    result = {}
    for routeRef, route in data.items():
        result[routeRef] = []
        for variantId in route:
            stops = route[variantId]
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
                ),
            )
    return result


def fetchApiRoutes() -> dict[RouteRef, list[APIUMWarszawaRouteResult]]:
    if API_UM_WARSZAWA_API_KEY is None:
        logging.error(
            "Missing API UM Warszawa api key. Set it as API_KEY environment variable",
        )
        return {}
    try:
        resourceId = "26b9ade1-f5d4-439e-84b4-9af37ab7ebf1"
        url = f"https://api.um.warszawa.pl/api/action/public_transport_routes/?apikey={API_UM_WARSZAWA_API_KEY}&resource_id={resourceId}"
        with logDuration("Downloading data from API UM Warszawa"):
            response = httpx.get(url)
            response.raise_for_status()
        with logDuration("Parsing API UM Warszawa JSON"):
            data = json.loads(response.text)["result"]
        return _parseApiUMData(data)
    except Exception:
        logging.exception("Failed to fetch data from API UM Warszawa")
        return {}
