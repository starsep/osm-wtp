from dataclasses import dataclass
from typing import Dict, List, Tuple

from distance import GeoPoint
from model.osm import OSMStop
from model.types import StopRef, StopName


@dataclass(frozen=True)
class GTFSStop(GeoPoint):
    ref: StopRef
    name: StopName


@dataclass(frozen=True)
class OSMAndGTFSComparisonResult:
    osmStops: Dict[StopRef, OSMStop]
    gtfsStops: Dict[StopRef, GTFSStop]
    osmStopRefsNotInGTFS: List[StopRef]
    gtfsStopRefsNotInOSM: List[StopRef]
    farAwayStops: List[Tuple[StopRef, int]]
