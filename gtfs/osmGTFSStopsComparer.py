import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Set, Tuple

from pyproj import Geod

from model.types import StopRef, StopName
from osm.OSMRelationAnalyzer import osmStopsWithLocation, OSMStop

gtfsPath = Path("../GTFS-Warsaw")


@dataclass
class GTFSStop:
    ref: StopRef
    name: StopName
    lat: float
    lon: float


wgs84Geod = Geod(ellps="WGS84")
STOP_DISTANCE_THRESHOLD = 100.0  # metres


def stopsDistance(osmStop: OSMStop, gtfsStop: GTFSStop) -> float:
    return wgs84Geod.inv(osmStop.lon, osmStop.lat, gtfsStop.lon, gtfsStop.lat)[2]


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
        distance = stopsDistance(osmStop=osmStops[ref], gtfsStop=gtfsStops[ref])
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
