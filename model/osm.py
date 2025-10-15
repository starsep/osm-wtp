from dataclasses import dataclass

from starsep_utils import GeoPoint

from model.types import StopName, StopRef


@dataclass(frozen=True)
class OSMStop(GeoPoint):
    ref: StopRef
    name: StopName
    osmId: int
    osmType: str

    @property
    def url(self) -> str:
        return f"https://osm.org/{self.osmType}/{self.osmId}"
