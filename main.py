from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from itertools import zip_longest
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

import overpy
from jinja2 import (
    Environment,
    select_autoescape,
    FileSystemLoader,
    StrictUndefined,
)
from tqdm import tqdm

from configuration import (
    OVERPASS_URL,
    cacheOverpass,
    WARSAW_PUBLIC_TRANSPORT_ID,
    MISSING_REF,
)
from model.stopData import StopData
from osm.utils import elementUrl
from warsaw.wtpScraper import (
    WTPLink,
    wtpDomain,
    wtpSeenLinks,
    scrapeHomepage,
    wtpMissingLastStop,
    wtpMissingLastStopRefNames,
    wtpStopRefs,
    scrapeLink,
)
from warsaw.wtpStopMapping import wtpStopMapping

overpassApi = overpy.Overpass(url=OVERPASS_URL)
startTime = datetime.now()


@cacheOverpass.memoize()
def getRelationDataFromOverpass():
    query = f"""
    [out:json][timeout:250];
    (
        relation(id:{WARSAW_PUBLIC_TRANSPORT_ID});
    );
    (._;>>;);
    out body;
    """
    return overpassApi.query(query)


@dataclass
class RouteResult:
    ref: str
    osmName: str
    osmId: str
    wtpLink: str
    osmStops: List[StopData]
    wtpStops: List[StopData]
    detour: bool
    new: bool
    short: bool
    unknownRoles: Set[str]
    construction: bool
    proposed: bool
    invalidRouteTag: bool


results: Dict[str, List[RouteResult]] = {}


allOSMRefs = set()
disusedStop = set()
manyLastStops = set()
mismatchOSMNameRef = set()
missingName = set()
missingRouteUrl = set()
missingRef = set()
unexpectedLink = set()
unexpectedNetwork = set()
unexpectedRef = set()

invalidWtpVariants = set()
osmWtpLinks: Set[Tuple[str, str, str]] = set()
wtpLinkDuplicates = set()

osmRefToName: Dict[str, Set[str]] = dict()
wtpRefToName: Dict[str, Set[str]] = dict()


def parseRef(tags) -> Optional[str]:
    refKeys = ["ref:wtp", "ref:ztm", "ref"]
    for refKey in refKeys:
        if refKey in tags:
            return tags[refKey]
    return None


def parseName(tags) -> Optional[str]:
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
class DiffRow:
    color: str
    refOSM: str
    nameOSM: str
    refOperator: str
    nameOperator: str


@dataclass
class RenderRouteResult:
    route: RouteResult
    diffRows: List[DiffRow]
    otherErrors: Set[str]


def processData():
    scrapeHomepage()
    for route in tqdm(getRelationDataFromOverpass().relations):
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
            if parsedLinkTuple in osmWtpLinks:
                wtpLinkDuplicates.add(WTPLink.fromTuple(parsedLinkTuple).url())
            osmWtpLinks.add(parsedLinkTuple)
        scrapingResult = scrapeLink(link)
        if scrapingResult.notAvailable:
            invalidWtpVariants.add((link, elementUrl(route)))
            continue
        osmStops = []
        unknownRoles = set()
        construction = False
        proposed = False
        invalidRouteTag = False
        for member in route.members:
            role: str = member.role
            element = member.resolve()
            tags = element.tags
            if role.startswith("platform") or role.startswith("stop"):
                element = member.resolve()
                for tag in element.tags:
                    if "disused" in tag:
                        disusedStop.add(elementUrl(element))
                osmStopRef = parseRef(tags)
                osmStopName = parseName(tags)
                if osmStopName is None:
                    missingName.add(elementUrl(element))
                    if osmStopRef is None:
                        missingRef.add((elementUrl(element), ""))
                    continue
                if osmStopRef is None:
                    missingRef.add((elementUrl(element), osmStopName))
                    continue
                if len(osmStopRef) != 6:
                    if (
                        "network" in tags
                        and tags["network"] == "ZTM Warszawa"
                    ):
                        unexpectedRef.add((elementUrl(element), osmStopRef))
                    continue
                if osmStopRef not in osmRefToName:
                    osmRefToName[osmStopRef] = set()
                osmRefToName[osmStopRef].add(osmStopName)
                stop = StopData(name=osmStopName, ref=osmStopRef)
                checkOSMNameMatchesRef(stop, elementUrl(element))
                if len(osmStops) == 0 or osmStops[-1].ref != stop.ref:
                    osmStops.append(stop)
                    allOSMRefs.add(stop.ref)
            elif len(role) > 0:
                unknownRoles.add(role)
            else:
                if "highway" not in tags and "railway" not in tags:
                    invalidRouteTag = True
                if "highway" in tags:
                    if tags["highway"] == "construction":
                        construction = True
                    if tags["highway"] == "proposed":
                        proposed = True
                if "railway" in tags:
                    if tags["railway"] == "construction":
                        construction = True
                    if tags["railway"] == "proposed":
                        proposed = True
        if routeRef not in results:
            results[routeRef] = []
        results[routeRef].append(
            RouteResult(
                ref=routeRef,
                osmName=route.tags["name"],
                osmId=route.id,
                osmStops=osmStops,
                wtpLink=link,
                wtpStops=scrapingResult.stops,
                detour=scrapingResult.detour,
                new=scrapingResult.new,
                short=scrapingResult.short,
                unknownRoles=unknownRoles,
                construction=construction,
                proposed=proposed,
                invalidRouteTag=invalidRouteTag,
            )
        )

    refs = sorted(results.keys(), key=lambda x: (len(x), x))
    renderResults = {}
    for routeRef in refs:
        detourOnlyErrors = True
        routeResults = []
        for route in results[routeRef]:
            osmRefs = [stop.ref for stop in route.osmStops]
            wtpRefs = [stop.ref for stop in route.wtpStops]
            for stop in route.wtpStops:
                if stop.ref not in wtpRefToName:
                    wtpRefToName[stop.ref] = set()
                wtpRefToName[stop.ref].add(stop.name)
            otherErrors = set()
            diffRows = []
            if len(route.unknownRoles) > 0:
                otherErrors.add(f"Nieznane role: {route.unknownRoles}")
            if route.construction:
                otherErrors.add("Trasa używa highway/railway=construction")
            if route.proposed:
                otherErrors.add("Trasa używa highway/railway=proposed")
            if route.invalidRouteTag:
                otherErrors.add("Trasa przebiega przez element bez tagu highway/railway")
            if osmRefs != wtpRefs:
                matcher = SequenceMatcher(None, osmRefs, wtpRefs)

                def writeTableRow(refOSM: str, refOperator: str):
                    nameOSM = (
                        list(osmRefToName[refOSM])[0]
                        if refOSM != MISSING_REF
                        else MISSING_REF
                    )
                    nameOperator = (
                        list(wtpRefToName[refOperator])[0]
                        if refOperator != MISSING_REF
                        else MISSING_REF
                    )
                    color = "inherit"
                    if refOSM == refOperator:
                        color = "inherit"
                    elif refOSM == MISSING_REF:
                        color = "green"
                    elif refOSM != MISSING_REF and refOperator != MISSING_REF:
                        color = "orange"
                    elif refOperator == MISSING_REF and nameOperator == MISSING_REF:
                        color = "red"
                    elif refOperator == MISSING_REF and nameOperator != MISSING_REF:
                        color = "orange" if nameOSM != nameOperator else "inherit"
                    diffRows.append(
                        DiffRow(
                            color=color,
                            refOSM=refOSM,
                            nameOSM=nameOSM,
                            refOperator=refOperator,
                            nameOperator=nameOperator,
                        )
                    )

                for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                    if tag == "equal":
                        for i, j in zip(range(i1, i2), range(j1, j2)):
                            writeTableRow(refOSM=osmRefs[i], refOperator=wtpRefs[j])
                    elif tag == "delete":
                        for i in range(i1, i2):
                            writeTableRow(refOSM=osmRefs[i], refOperator=MISSING_REF)
                    elif tag == "insert":
                        for j in range(j1, j2):
                            writeTableRow(refOSM=MISSING_REF, refOperator=wtpRefs[j])
                    elif tag == "replace":
                        for i, j in zip_longest(
                            range(i1, i2), range(j1, j2), fillvalue=None
                        ):
                            writeTableRow(
                                refOSM=osmRefs[i] if i is not None else MISSING_REF,
                                refOperator=wtpRefs[j]
                                if j is not None
                                else MISSING_REF,
                            )
                if not route.detour:
                    detourOnlyErrors = False
            error = len(otherErrors) > 0 or len(routeResults) > 0
            if error:
                routeResults.append(
                    RenderRouteResult(route=route, diffRows=diffRows, otherErrors=otherErrors)
                )
            renderResults[routeRef] = dict(
                routeMismatch=osmRefs != wtpRefs, error=error, detourOnlyErrors=detourOnlyErrors, routeResults=routeResults,
            )
    notLinkedWtpUrls: Set[str] = set()
    for link in wtpSeenLinks - osmWtpLinks:
        wtpLinkParams = WTPLink.fromTuple(link)
        if wtpLinkParams.line not in ["M1", "M2"]:
            notLinkedWtpUrls.add(wtpLinkParams.url())

    with Path("../osm-wtp/index.html").open("w") as f:
        env = Environment(
            loader=FileSystemLoader(searchpath="./"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )
        template = env.get_template("index.j2")
        endTime = datetime.now()
        generationSeconds = int((endTime - startTime).total_seconds())
        f.write(
            template.render(
                refs=refs,
                startTime=startTime.isoformat(timespec="seconds"),
                generationSeconds=generationSeconds,
                renderResults=renderResults,
                disusedStop=disusedStop,
                invalidWtpVariants=invalidWtpVariants,
                wtpManyLastStops=manyLastStops,
                notUniqueOSMNames={
                    ref: names for ref, names in osmRefToName.items() if len(names) > 1
                },
                notUniqueWTPNames={
                    ref: names for ref, names in wtpRefToName.items() if len(names) > 1
                },
                mismatchOSMNameRef=mismatchOSMNameRef,
                wtpMissingLastStop=wtpMissingLastStop,
                missingLastStopRefNames=list(sorted(wtpMissingLastStopRefNames)),
                missingName=missingName,
                missingRouteUrl=missingRouteUrl,
                missingRef=missingRef,
                missingRefsInOSM=[
                    (ref, list(wtpRefToName[ref])[0])
                    for ref in sorted(wtpStopRefs - allOSMRefs)
                ],
                notLinkedWtpUrls=sorted(list(notLinkedWtpUrls)),
                unexpectedLink=unexpectedLink,
                unexpectedNetwork=unexpectedNetwork,
                unexpectedRef=unexpectedRef,
                wtpStopMapping=wtpStopMapping,
                wtpLinkDuplicates=wtpLinkDuplicates,
            )
        )


if __name__ == "__main__":
    processData()
