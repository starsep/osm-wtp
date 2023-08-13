from dataclasses import dataclass
from typing import Optional, Dict, List, Set, Tuple, cast

from tqdm import tqdm

import logger
from distance import GeoPoint
from logger import log_duration
from model.stopData import StopData
from model.types import StopName, RouteRef, StopRef
from osm.overpass import (
    Node,
    Element,
    OverpassResult,
    Way,
    downloadOverpassData,
    Relation,
)
from warsaw.scrapedOSMRoute import ScrapedOSMRoute
from warsaw.warsawConstants import WKD_WIKIDATA, KM_WIKIDATA
from warsaw.wtpLastStopRefs import (
    LastStopRefsResult,
    generateLastStopRefs,
    lastStopRef,
)
from warsaw.wtpScraper import wtpDomain, WTPLink, scrapeLink

mismatchOSMNameRef = set()


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
    osmId: int
    operatorLink: str
    osmStops: List[StopData]
    operatorStops: List[StopData]
    detour: bool
    new: bool
    short: bool
    unknownRoles: Set[str]
    otherErrors: Set[str]
    routeType: str


@dataclass
class OSMStop(GeoPoint):
    ref: StopRef
    name: StopName


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


def _scrapeOSMRoute(route: Relation) -> Optional[ScrapedOSMRoute]:
    tags = route.tags
    routeRef = parseRef(tags)
    if (
        "type" not in tags
        or "route" not in tags
        or tags["type"] != "route"
        or routeRef is None
        or tags["route"] in ["tracks", "subway", "train", "railway"]
    ):
        return None
    if "url" not in tags:
        if not (
            "operator:wikidata" in tags
            and tags["operator:wikidata"] in [KM_WIKIDATA, WKD_WIKIDATA]
        ):
            missingRouteUrl.add((route.url, tags.get("name", "")))
        return None
    if "network" in tags and tags["network"] != "ZTM Warszawa":
        unexpectedNetwork.add((route.url, tags["network"]))
    link = tags["url"]
    if wtpDomain not in link:
        unexpectedLink.add((route.url, link))
        return None
    parsedLink = WTPLink.parseWTPRouteLink(link)
    if parsedLink is not None:
        parsedLinkTuple = parsedLink.toTuple()
        if parsedLinkTuple in osmOperatorLinks:
            wtpLinkDuplicates.add(WTPLink.fromTuple(parsedLinkTuple).url())
        osmOperatorLinks.add(parsedLinkTuple)
    scrapingResult = scrapeLink(link)
    if (
        scrapingResult is None
        or scrapingResult.notAvailable
        or len(scrapingResult.stops) == 0
    ):
        invalidOperatorVariants.add((link, route.url))
        return None
    return ScrapedOSMRoute(
        route=route, wtpResult=scrapingResult, routeRef=routeRef, link=link
    )


@log_duration
def scrapeOSMRoutes(overpassResult: OverpassResult) -> List[ScrapedOSMRoute]:
    logger.info("🔧 Scraping WTP Routes")
    result = []
    for route in tqdm(overpassResult.relations.values()):
        scrapedOSMRoute = _scrapeOSMRoute(route)
        if scrapedOSMRoute is not None:
            result.append(scrapedOSMRoute)
    return result


@log_duration
def addLastStopRefs(
    scrapedRoutes: List[ScrapedOSMRoute],
    lastStopRefsResult: LastStopRefsResult,
):
    for route in scrapedRoutes:
        route.wtpResult.stops[-1].ref = lastStopRef(
            route.wtpResult.stops[-1].name,
            route.wtpResult.stops[-2].ref,
            lastStopRefsResult,
        )


@log_duration
def analyzeOSMRelations() -> OSMResults:
    logger.info("🔍 Starting analyzeOSMRelations")
    results: OSMResults = {}
    overpassResult = downloadOverpassData()
    scrapedOSMRoutes = scrapeOSMRoutes(overpassResult)
    lastStopRefs = generateLastStopRefs(scrapedRoutes=scrapedOSMRoutes)
    addLastStopRefs(scrapedOSMRoutes, lastStopRefs)
    for scrapedRoute in tqdm(scrapedOSMRoutes):
        route = scrapedRoute.route
        routeRef = scrapedRoute.routeRef
        link = scrapedRoute.link
        scrapingResult = scrapedRoute.wtpResult
        osmStops = []
        unknownRoles = set()
        otherErrors: Set[str] = set()
        stopNodes: Set[Node] = set()
        routeWays: List[Element] = list()
        for member in route.members:
            role: str = member.role
            element = overpassResult.resolve(member)
            tags = element.tags
            if role is None or len(role) == 0:
                routeWays.append(element)
            elif role.startswith("platform") or role.startswith("stop"):
                element = overpassResult.resolve(member)
                for tag in element.tags:
                    if "disused" in tag:
                        disusedStop.add(element.url)
                osmStopRef = parseRef(tags)
                osmStopName = parseName(tags)
                if osmStopName is None:
                    if not ("railway" in tags and tags["railway"] == "platform"):
                        missingName.add(element.url)
                    if osmStopRef is None:
                        missingStopRef.add((element.url, ""))
                    continue
                if osmStopRef is None:
                    missingStopRef.add((element.url, osmStopName))
                    continue
                if len(osmStopRef) != 6:
                    if "network" in tags and tags["network"] == "ZTM Warszawa":
                        unexpectedStopRef.add((element.url, osmStopRef))
                    continue
                if osmStopRef not in osmRefToName:
                    osmRefToName[osmStopRef] = set()
                osmRefToName[osmStopRef].add(osmStopName)
                stop = StopData(name=osmStopName, ref=osmStopRef)
                checkOSMNameMatchesRef(stop, element.url)
                # prefer stop to platform
                if osmStopRef not in osmStopsWithLocation or role == "stop":
                    coords = element.center(overpassResult)
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
                    if element.type != "node":
                        otherErrors.add("Stop niebędący punktem")
                    else:
                        stopNodes.add(cast(Node, element))
            elif len(role) > 0:
                unknownRoles.add(role)
        validateRoute(routeWays, stopNodes, otherErrors, overpassResult)
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
                routeType=route.tags["route"],
            )
        )
    return results


def validateRoute(
    routeWays: List[Element],
    stopNodes: Set[Node],
    otherErrors: Set[str],
    overpassResult: OverpassResult,
):
    variantWayNodes: Set[Node] = set()
    validatedWays: List[Way] = []
    for way in routeWays:
        if way.type == "way":
            way = cast(Way, way)
            validateWay(way, otherErrors, variantWayNodes, overpassResult)
            validatedWays.append(way)
        else:
            otherErrors.add("Element bez roli niebędący linią")
    validateRouteGeometry(validatedWays=validatedWays, otherErrors=otherErrors)
    checkStopNodesWithinRoute(
        stopNodes=stopNodes, variantWayNodes=variantWayNodes, otherErrors=otherErrors
    )


def validateRouteGeometry(validatedWays: List[Way], otherErrors: Set[str]):
    # TODO: direction
    previousWay = validatedWays[0]
    for way in validatedWays[1:]:
        if not matchWayNode(
            previousWay=previousWay, currentWay=way, otherErrors=otherErrors
        ):
            otherErrors.add("Trasa jest niespójna")
        previousWay = way


def matchWayNode(previousWay: Way, currentWay: Way, otherErrors: Set[str]) -> bool:
    if matchRoundabout(previousWay, currentWay, otherErrors) or matchRoundabout(
        currentWay, previousWay, otherErrors
    ):
        return True
    if "no" in [
        previousWay.tags.get("oneway:bus", ""),
        previousWay.tags.get("oneway:psv", ""),
    ]:
        return True
    previousStart = previousWay.nodes[0]
    previousEnd = previousWay.nodes[-1]
    currentStart = currentWay.nodes[0]
    currentEnd = currentWay.nodes[-1]
    if previousEnd == currentStart or previousEnd == currentEnd:
        if "oneway" in previousWay.tags and previousWay.tags["oneway"] == "-1":
            otherErrors.add("Jednokierunkowa droga używana pod prąd")
        return True
    if previousStart == currentStart or previousStart == currentEnd:
        if "oneway" in previousWay.tags and previousWay.tags["oneway"] == "yes":
            otherErrors.add("Jednokierunkowa droga używana pod prąd")
        return True
    return False


def matchRoundabout(roundabout: Way, way: Way, otherErrors: Set[str]) -> bool:
    if (
        "junction" not in roundabout.tags
        or roundabout.tags["junction"] != "roundabout"
        or roundabout.nodes[0] != roundabout.nodes[-1]
    ):
        return False
    endingWayNodes = [way.nodes[0], way.nodes[-1]]
    for node in roundabout.nodes:
        if node in endingWayNodes:
            otherErrors.add("Niepodzielone rondo jest częścią trasy")
            return True
    return False


def validateWay(
    way: Way,
    otherErrors: Set[str],
    variantWayNodes: Set[Node],
    overpassResult: OverpassResult,
):
    for node in way.nodes:
        variantWayNodes.add(overpassResult.nodes[node])
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
    stopNodes: Set[Node],
    variantWayNodes: Set[Node],
    otherErrors: Set[str],
):
    stopsNotWithinRoute = stopNodes - variantWayNodes
    if len(stopsNotWithinRoute) > 0:
        otherErrors.add("Punkty zatrzymania nie należą do trasy")
