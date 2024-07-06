import csv
from pathlib import Path
from typing import Dict

from starsep_utils import haversine
from model.gtfs import GTFSStop, OSMAndGTFSComparisonResult
from model.types import StopRef
from osm.OSMRelationAnalyzer import osmStopsWithLocation

gtfsPath = Path("./GTFS-Warsaw")


STOP_DISTANCE_THRESHOLD = 100.0  # metres


def compareOSMAndGTFSStops(
    gtfsStops: Dict[StopRef, GTFSStop],
) -> OSMAndGTFSComparisonResult:
    osmStops = osmStopsWithLocation
    osmStopRefsNotInGTFS = list(sorted(osmStops.keys() - gtfsStops.keys()))
    gtfsStopRefsNotInOSM = list(sorted(gtfsStops.keys() - osmStops.keys()))
    commonRefs = gtfsStops.keys() & osmStops.keys()
    farAwayStops = []
    for ref in sorted(commonRefs):
        distance = haversine(osmStops[ref], gtfsStops[ref])
        if distance > STOP_DISTANCE_THRESHOLD:
            farAwayStops.append((ref, int(round(distance))))
    return OSMAndGTFSComparisonResult(
        osmStops=osmStops,
        gtfsStops=gtfsStops,
        osmStopRefsNotInGTFS=osmStopRefsNotInGTFS,
        gtfsStopRefsNotInOSM=gtfsStopRefsNotInOSM,
        farAwayStops=farAwayStops,
    )


def shouldIgnoreGTFSRef(ref: StopRef) -> bool:
    return len(ref) != 6 or not ref.isnumeric()


def loadGTFSStops() -> Dict[StopRef, GTFSStop]:
    result = dict()
    with (gtfsPath / "stops.txt").open() as stopsFile:
        stopsReader = csv.DictReader(stopsFile, delimiter=",")
        for stop in stopsReader:
            ref = stop["stop_id"]
            if shouldIgnoreGTFSRef(ref):
                continue
            result[ref] = GTFSStop(
                ref=ref,
                name=stop["stop_name"],
                lat=float(stop["stop_lat"]),
                lon=float(stop["stop_lon"]),
            )
    return result
