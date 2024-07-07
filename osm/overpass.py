import abc
import json
import logging
from dataclasses import dataclass
from typing import Tuple, List, Dict

import httpx

from starsep_utils import logDuration
from configuration import OVERPASS_URL
from warsaw.warsawConstants import WARSAW_PUBLIC_TRANSPORT_ID


class KeyDict(dict):
    def __hash__(self):
        return hash(frozenset(self.items()))


@dataclass(frozen=True)
class Element(abc.ABC):
    id: int
    type: str
    tags: KeyDict[str, str]

    @property
    def url(self):
        return f"https://osm.org/{self.type}/{self.id}"

    @abc.abstractmethod
    def center(self, overpassResult: "OverpassResult") -> Tuple[float, float]:
        raise NotImplementedError


@dataclass(frozen=True)
class Node(Element):
    lat: float
    lon: float

    def center(self, overpassResult: "OverpassResult") -> Tuple[float, float]:
        return self.lat, self.lon


@dataclass(frozen=True)
class Way(Element):
    nodes: List[int]

    def center(self, overpassResult: "OverpassResult") -> Tuple[float, float]:
        centers = [
            overpassResult.nodes[nodeId].center(overpassResult) for nodeId in self.nodes
        ]
        lat = sum(center[0] for center in centers) / len(centers)
        lon = sum(center[1] for center in centers) / len(centers)
        return lat, lon


@dataclass(frozen=True)
class RelationMember:
    type: str
    id: int
    role: str


@dataclass(frozen=True)
class Relation(Element):
    members: List[RelationMember]

    def center(self, overpassResult: "OverpassResult") -> Tuple[float, float]:
        raise NotImplementedError


@dataclass(frozen=True)
class OverpassResult:
    nodes: Dict[int, Node]
    ways: Dict[int, Way]
    relations: Dict[int, Relation]

    def resolve(self, member: RelationMember) -> Element:
        if member.type == "node":
            return self.nodes[member.id]
        if member.type == "way":
            return self.ways[member.id]
        if member.type == "relation":
            return self.relations[member.id]
        raise ValueError(member.type)


def _getOverpassHttpx():
    query = f"""
    [out:json][timeout:250];
    (
        relation(id:{WARSAW_PUBLIC_TRANSPORT_ID});
    );
    (._;>>;);
    out body;
    """
    with logDuration("Downloading data from Overpass"):
        response = httpx.post(OVERPASS_URL, data=dict(data=query))
        response.raise_for_status()
    with logDuration("Parsing Overpass JSON"):
        return json.loads(response.text)["elements"]


@logDuration
def _parseOverpassData(parsedElements: List[Dict]):
    nodes, ways, relations = dict(), dict(), dict()
    for element in parsedElements:
        if element["type"] == "node":
            nodes[element["id"]] = Node(
                id=element["id"],
                type=element["type"],
                lat=element["lat"],
                lon=element["lon"],
                tags=KeyDict(element.get("tags", dict())),
            )
        if element["type"] == "way":
            ways[element["id"]] = Way(
                id=element["id"],
                type=element["type"],
                nodes=element["nodes"],
                tags=KeyDict(element.get("tags", dict())),
            )
        if element["type"] == "relation":
            members = [
                RelationMember(
                    type=member["type"], id=member["ref"], role=member["role"]
                )
                for member in element["members"]
            ]
            relations[element["id"]] = Relation(
                id=element["id"],
                type=element["type"],
                members=members,
                tags=KeyDict(element.get("tags", dict())),
            )
    return OverpassResult(nodes=nodes, ways=ways, relations=relations)


def downloadOverpassData():
    logging.info("⏬ Overpass Download")
    return _parseOverpassData(_getOverpassHttpx())
