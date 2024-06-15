from dataclasses import dataclass

from distance import GeoPoint
from model.types import StopRef, StopName


@dataclass(frozen=True)
class OSMStop(GeoPoint):
    ref: StopRef
    name: StopName
    osmId: int
    osmType: str

    @property
    def url(self):
        return f"https://osm.org/{self.osmType}/{self.osmId}"
