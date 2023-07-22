import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple

from distance import GeoPoint, geoDistance
from model.types import StopRef, StopName
from osm.OSMRelationAnalyzer import osmStopsWithLocation, OSMStop

gtfsPath = Path("../GTFS-Warsaw")


@dataclass
class GTFSStop(GeoPoint):
    ref: StopRef
    name: StopName


STOP_DISTANCE_THRESHOLD = 100.0  # metres



@dataclass
class OSMAndGTFSComparisonResult:
    osmStops: Dict[StopRef, OSMStop]
    gtfsStops: Dict[StopRef, GTFSStop]
    osmStopRefsNotInGTFS: List[StopRef]
    gtfsStopRefsNotInOSM: List[StopRef]
    farAwayStops: List[Tuple[StopRef, int]]


def compareOSMAndGTFSStops() -> OSMAndGTFSComparisonResult:
    osmStops = osmStopsWithLocation
    gtfsStops = loadGTFSStops()
    osmStopRefsNotInGTFS = list(sorted(osmStops.keys() - gtfsStops.keys()))
    gtfsStopRefsNotInOSM = list(sorted(gtfsStops.keys() - osmStops.keys()))
    commonRefs = gtfsStops.keys() & osmStops.keys()
    farAwayStops = []
    for ref in sorted(commonRefs):
        distance = geoDistance(osmStops[ref], gtfsStops[ref])
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
