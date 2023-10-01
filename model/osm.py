from dataclasses import dataclass

from distance import GeoPoint
from model.types import StopRef, StopName


@dataclass
class OSMStop(GeoPoint):
    ref: StopRef
    name: StopName
