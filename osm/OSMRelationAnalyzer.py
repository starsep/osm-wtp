from dataclasses import dataclass
from typing import Optional, Dict, List, Set, Tuple, cast

import overpy
from diskcache import Cache

from configuration import OVERPASS_URL, cacheDirectory
from model.stopData import StopData
from model.types import StopName, RouteRef, StopRef
from osm.utils import elementUrl, coordinatesOfStop
from warsaw.warsawConstants import WARSAW_PUBLIC_TRANSPORT_ID, WKD_WIKIDATA, KM_WIKIDATA
from warsaw.wtpScraper import wtpDomain, WTPLink, scrapeLink

mismatchOSMNameRef = set()

overpassApi = overpy.Overpass(url=OVERPASS_URL)
cacheOverpass = Cache(str(cacheDirectory / "overpass"))


@cacheOverpass.memoize()
def getRelationDataFromOverpass():
    query = f"""
    [out:xml][timeout:250];
    (
        relation(id:{WARSAW_PUBLIC_TRANSPORT_ID});
    );
    (._;>>;);
    out body;
    """
    return overpassApi.query(query)


def parseRef(tags) -> Optional[str]:
    refKeys = ["ref:wtp", "ref:ztm", "ref"]
    for refKey in refKeys:
        if refKey in tags:
            return tags[refKey]
    return None


def parseName(tags) -> Optional[StopName]:
    nameKeys = ["name:wtp", "name:ztm", "name"]
    for nameKey in nameKeys:
        if nameKey in tags:
            return tags[nameKey]
    return None


def checkOSMNameMatchesRef(stop: StopData, url: str):
    localRef = stop.ref[-2]
    nameSuffix = stop.name[-2]
    if localRef != nameSuffix:
        mismatchOSMNameRef.add((stop.ref, stop.name, url))


@dataclass
class VariantResult:
    ref: RouteRef
    osmName: str
    osmId: str
    operatorLink: str
    osmStops: List[StopData]
    operatorStops: List[StopData]
    detour: bool
    new: bool
    short: bool
    unknownRoles: Set[str]
    otherErrors: Set[str]


@dataclass
class OSMStop:
    ref: StopRef
    name: StopName
    lat: float
    lon: float


allOSMRefs = set()
disusedStop = set()
manyLastStops = set()
missingName = set()
missingRouteUrl = set()
missingStopRef = set()
unexpectedLink = set()
unexpectedNetwork = set()
unexpectedStopRef = set()
osmStopsWithLocation: Dict[StopRef, OSMStop] = dict()

invalidOperatorVariants = set()
osmOperatorLinks: Set[Tuple[str, str, str]] = set()
wtpLinkDuplicates = set()

osmRefToName: Dict[StopRef, Set[StopName]] = dict()

OSMResults = Dict[RouteRef, List[VariantResult]]


def analyzeOSMRelations() -> OSMResults:
    results: OSMResults = {}
    for route in getRelationDataFromOverpass().relations:
        tags = route.tags
        routeRef = parseRef(tags)
        if (
            "type" not in tags
            or "route" not in tags
            or tags["type"] != "route"
            or routeRef is None
            or tags["route"] == "tracks"
            or tags["route"] == "subway"
        ):
            continue
        if "url" not in tags:
            if not (
                "operator:wikidata" in tags
                and tags["operator:wikidata"] in [KM_WIKIDATA, WKD_WIKIDATA]
            ):
                missingRouteUrl.add((elementUrl(route), tags.get("name", "")))
            continue
        if "network" in tags and tags["network"] != "ZTM Warszawa":
            unexpectedNetwork.add((elementUrl(route), tags["network"]))
        link = tags["url"]
        if wtpDomain not in link:
            unexpectedLink.add((elementUrl(route), link))
            continue
        parsedLink = WTPLink.parseWTPRouteLink(link)
        if parsedLink is not None:
            parsedLinkTuple = parsedLink.toTuple()
            if parsedLinkTuple in osmOperatorLinks:
                wtpLinkDuplicates.add(WTPLink.fromTuple(parsedLinkTuple).url())
            osmOperatorLinks.add(parsedLinkTuple)
        scrapingResult = scrapeLink(link)
        if scrapingResult.notAvailable:
            invalidOperatorVariants.add((link, elementUrl(route)))
            continue
        osmStops = []
        unknownRoles = set()
        otherErrors: Set[str] = set()
        stopNodes: Set[overpy.Node] = set()
        routeWays: List[overpy.Element] = list()
        for member in route.members:
            role: str = member.role
            element = member.resolve()
            tags = element.tags
            if role is None or len(role) == 0:
                routeWays.append(element)
            elif role.startswith("platform") or role.startswith("stop"):
                element = member.resolve()
                for tag in element.tags:
                    if "disused" in tag:
                        disusedStop.add(elementUrl(element))
                osmStopRef = parseRef(tags)
                osmStopName = parseName(tags)
                if osmStopName is None:
                    if not ("railway" in tags and tags["railway"] == "platform"):
                        missingName.add(elementUrl(element))
                    if osmStopRef is None:
                        missingStopRef.add((elementUrl(element), ""))
                    continue
                if osmStopRef is None:
                    missingStopRef.add((elementUrl(element), osmStopName))
                    continue
                if len(osmStopRef) != 6:
                    if "network" in tags and tags["network"] == "ZTM Warszawa":
                        unexpectedStopRef.add((elementUrl(element), osmStopRef))
                    continue
                if osmStopRef not in osmRefToName:
                    osmRefToName[osmStopRef] = set()
                osmRefToName[osmStopRef].add(osmStopName)
                stop = StopData(name=osmStopName, ref=osmStopRef)
                checkOSMNameMatchesRef(stop, elementUrl(element))
                # prefer stop to platform
                if osmStopRef not in osmStopsWithLocation or role == "stop":
                    coords = coordinatesOfStop(element)
                    if coords is not None:
                        lat, lon = coords
                        osmStopsWithLocation[osmStopRef] = OSMStop(
                            ref=osmStopRef,
                            name=osmStopName,
                            lat=lat,
                            lon=lon,
                        )
                if len(osmStops) == 0 or osmStops[-1].ref != stop.ref:
                    osmStops.append(stop)
                    allOSMRefs.add(stop.ref)
                if role.startswith("stop"):
                    if type(element) != overpy.Node:
                        otherErrors.add("Stop niebędący punktem")
                    else:
                        stopNodes.add(element)
            elif len(role) > 0:
                unknownRoles.add(role)
        validateRoute(routeWays, stopNodes, otherErrors)
        if routeRef not in results:
            results[routeRef] = []
        results[routeRef].append(
            VariantResult(
                ref=routeRef,
                osmName=route.tags["name"],
                osmId=route.id,
                osmStops=osmStops,
                operatorLink=link,
                operatorStops=scrapingResult.stops,
                detour=scrapingResult.detour,
                new=scrapingResult.new,
                short=scrapingResult.short,
                unknownRoles=unknownRoles,
                otherErrors=otherErrors,
            )
        )
    return results


def validateRoute(
    routeWays: List[overpy.Element], stopNodes: Set[overpy.Node], otherErrors: Set[str]
):
    variantWayNodes: Set[overpy.Node] = set()
    validatedWays: List[overpy.Way] = []
    for way in routeWays:
        if type(way) == overpy.Way:
            way = cast(overpy.Way, way)
            validateWay(way, otherErrors, variantWayNodes)
            validatedWays.append(way)
        else:
            otherErrors.add("Element bez roli niebędący linią")
    validateRouteGeometry(validatedWays=validatedWays, otherErrors=otherErrors)
    checkStopNodesWithinRoute(
        stopNodes=stopNodes, variantWayNodes=variantWayNodes, otherErrors=otherErrors
    )


def validateRouteGeometry(validatedWays: List[overpy.Way], otherErrors: Set[str]):
    # TODO: direction
    previousWay = validatedWays[0]
    for way in validatedWays[1:]:
        if not matchWayNode(
            previousWay=previousWay, currentWay=way, otherErrors=otherErrors
        ):
            otherErrors.add("Trasa jest niespójna")
        previousWay = way


def matchWayNode(
    previousWay: overpy.Way, currentWay: overpy.Way, otherErrors: Set[str]
) -> bool:
    if matchRoundabout(previousWay, currentWay, otherErrors) or matchRoundabout(
        currentWay, previousWay, otherErrors
    ):
        return True
    if "no" in [previousWay.tags.get("oneway:bus", ""), previousWay.tags.get("oneway:psv", "")]:
        return True
    previousStart = previousWay.nodes[0].id
    previousEnd = previousWay.nodes[-1].id
    currentStart = currentWay.nodes[0].id
    currentEnd = currentWay.nodes[-1].id
    if previousEnd == currentStart or previousEnd == currentEnd:
        if "oneway" in previousWay.tags and previousWay.tags["oneway"] == "-1":
            otherErrors.add("Jednokierunkowa droga używana pod prąd")
        return True
    if previousStart == currentStart or previousStart == currentEnd:
        if "oneway" in previousWay.tags and previousWay.tags["oneway"] == "yes":
            otherErrors.add("Jednokierunkowa droga używana pod prąd")
        return True
    return False


def matchRoundabout(
    roundabout: overpy.Way, way: overpy.Way, otherErrors: Set[str]
) -> bool:
    if (
        "junction" not in roundabout.tags
        or roundabout.tags["junction"] != "roundabout"
        or roundabout.nodes[0].id != roundabout.nodes[-1].id
    ):
        return False
    endingWayNodes = [way.nodes[0].id, way.nodes[-1].id]
    for node in roundabout.nodes:
        if node.id in endingWayNodes:
            otherErrors.add("Niepodzielone rondo jest częścią trasy")
            return True
    return False


def validateWay(
    way: overpy.Way, otherErrors: Set[str], variantWayNodes: Set[overpy.Node]
):
    for node in way.nodes:
        variantWayNodes.add(node)
    tags = way.tags
    if "highway" not in tags and "railway" not in tags:
        otherErrors.add("Trasa przebiega przez element bez tagu highway/railway")
    if "highway" in tags:
        if tags["highway"] == "construction":
            otherErrors.add("Trasa używa highway=construction")
        if tags["highway"] == "proposed":
            otherErrors.add("Trasa używa highway=proposed")
    if "railway" in tags:
        if tags["railway"] == "construction":
            otherErrors.add("Trasa używa railway=construction")
        if tags["railway"] == "proposed":
            otherErrors.add("Trasa używa railway=proposed")
    validateAccessTags(tags, otherErrors)


def validateAccessTags(tags, otherErrors: Set[str]):
    if (
        "access" in tags
        and tags["access"] == "no"
        and ("bus" not in tags or tags["bus"] not in ["yes", "designated"])
        and ("psv" not in tags or tags["psv"] not in ["yes", "designated"])
    ):
        otherErrors.add("access=no bez bus/psv=yes/designated")


def checkStopNodesWithinRoute(
    stopNodes: Set[overpy.Node],
    variantWayNodes: Set[overpy.Node],
    otherErrors: Set[str],
):
    stopsNotWithinRoute = stopNodes - variantWayNodes
    if len(stopsNotWithinRoute) > 0:
        otherErrors.add("Punkty zatrzymania nie należą do trasy")
