from dataclasses import dataclass

from starsep_utils import GeoPoint

from model.osm import OSMStop
from model.types import StopName, StopRef


@dataclass(frozen=True)
class GTFSStop(GeoPoint):
    ref: StopRef
    name: StopName


@dataclass(frozen=True)
class OSMAndGTFSComparisonResult:
    osmStops: dict[StopRef, OSMStop]
    gtfsStops: dict[StopRef, GTFSStop]
    osmStopRefsNotInGTFS: list[StopRef]
    gtfsStopRefsNotInOSM: list[StopRef]
    farAwayStops: list[tuple[StopRef, int]]
