from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from itertools import zip_longest
from pathlib import Path
from typing import Dict, List
from urllib import parse

import httpx
import overpy
from bs4 import BeautifulSoup
from jinja2 import (
    Environment,
    PackageLoader,
    select_autoescape,
    FileSystemLoader,
    Undefined,
    StrictUndefined,
)
from tqdm import tqdm

from configuration import (
    OVERPASS_URL,
    cacheOverpass,
    cacheWTP,
    WARSAW_PUBLIC_TRANSPORT_ID,
)

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


@cacheWTP.memoize()
def fetchWtpWebsite(link: str):
    return httpx.get(link, follow_redirects=True).text


@dataclass
class StopData:
    name: str
    ref: str


@dataclass
class RouteResult:
    ref: str
    osmName: str
    osmId: str
    wtpLink: str
    osmStops: List[StopData]
    wtpStops: List[StopData]


results: Dict[str, List[RouteResult]] = {}

MISSING_REF = "-"


def elementUrl(element: overpy.Element) -> str:
    if type(element) == overpy.Node:
        return f"https://osm.org/node/{element.id}"
    elif type(element) == overpy.Way:
        return f"https://osm.org/way/{element.id}"
    elif type(element) == overpy.Relation:
        return f"https://osm.org/relation/{element.id}"
    else:
        print(f"Unexpected overpy type: {type(element)}")


disusedStop = set()
manyLastStops = set()
missingLastStop = set()
missingName = set()
missingRouteUrl = set()
missingRef = set()
unexpectedLink = set()
unexpectedNetwork = set()
unexpectedRef = set()

for route in tqdm(getRelationDataFromOverpass().relations):
    wtpStops = []
    tags = route.tags
    if (
        "type" not in tags
        or "route" not in tags
        or tags["type"] != "route"
        or "ref" not in tags
    ):
        continue
    ref = tags["ref"]
    if "url" not in tags:
        missingRouteUrl.add(elementUrl(route))
        continue
    if "network" in tags and tags["network"] != "ZTM Warszawa":
        unexpectedNetwork.add((elementUrl(route), tags["network"]))
    link = tags["url"]
    if "wtp.waw.pl" not in link:
        unexpectedLink.add((elementUrl(route), link))
        continue
    content = BeautifulSoup(fetchWtpWebsite(link), features="html.parser")
    for stopLink in content.select("a.timetable-link.active"):
        stopName = stopLink.text.strip()
        stopLink = stopLink.get("href")
        stopLinkArgs = parse.parse_qs(parse.urlparse(stopLink).query)
        stopRef = stopLinkArgs["wtp_st"][0] + stopLinkArgs["wtp_pt"][0]
        wtpStops.append(StopData(name=stopName, ref=stopRef))
    lastStop = content.select("div.timetable-route-point.name.active.follow.disabled")
    if len(lastStop) == 0:
        missingLastStop.add((elementUrl(route), link))
        continue
    if len(lastStop) > 1:
        manyLastStops.add((link, lastStop))
        continue
    for stopLink in lastStop:
        stopName = stopLink.text.strip()
        wtpStops.append(StopData(name=stopName, ref=MISSING_REF))
    osmStops = []
    for member in route.members:
        role: str = member.role
        if role.startswith("platform") or role.startswith("stop"):
            element = member.resolve()
            for tag in element.tags:
                if "disused" in tag:
                    disusedStop.add(elementUrl(element))
            if "name" not in element.tags:
                missingName.add(elementUrl(element))
                if "ref" not in element.tags:
                    missingRef.add(elementUrl(element))
                continue
            if "ref" not in element.tags:
                missingRef.add(elementUrl(element))
                continue
            if len(element.tags["ref"]) != 6:
                if (
                    "network" in element.tags
                    and element.tags["network"] == "ZTM Warszawa"
                ):
                    unexpectedRef.add((elementUrl(element), element.tags["ref"]))
                continue
            stop = StopData(name=element.tags["name"], ref=element.tags["ref"])
            if len(osmStops) == 0 or osmStops[-1].ref != stop.ref:
                osmStops.append(stop)
    if ref not in results:
        results[ref] = []
    results[ref].append(
        RouteResult(
            ref=ref,
            osmName=route.tags["name"],
            osmId=route.id,
            osmStops=osmStops,
            wtpLink=link,
            wtpStops=wtpStops,
        )
    )


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


refs = sorted(results.keys(), key=lambda x: (len(x), x))
renderResults = {}
for ref in refs:
    renderResults[ref] = dict(success=True, routeResults=[])
    for route in results[ref]:
        osmRefs = [stop.ref for stop in route.osmStops]
        wtpRefs = [stop.ref for stop in route.wtpStops]
        osmNames = {stop.ref: stop.name for stop in route.osmStops}
        wtpNames = {stop.ref: stop.name for stop in route.wtpStops}
        diffRows = []
        if osmRefs[:-1] != wtpRefs[:-1]:
            matcher = SequenceMatcher(None, osmRefs, wtpRefs)

            def writeTableRow(refOSM: str, refOperator: str):
                nameOSM = osmNames[refOSM] if refOSM != MISSING_REF else MISSING_REF
                nameOperator = (
                    wtpNames[refOperator] if refOperator != MISSING_REF else MISSING_REF
                )
                if refOSM == osmRefs[-1] and refOperator == MISSING_REF:
                    nameOperator = wtpNames[wtpRefs[-1]]
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
                            refOperator=wtpRefs[j] if j is not None else MISSING_REF,
                        )
            renderResults[ref]["success"] = False
            renderResults[ref]["routeResults"].append(
                RenderRouteResult(route=route, diffRows=diffRows)
            )

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
            manyLastStops=manyLastStops,
            missingLastStop=missingLastStop,
            missingName=missingName,
            missingRouteUrl=missingRouteUrl,
            missingRef=missingRef,
            unexpectedLink=unexpectedLink,
            unexpectedNetwork=unexpectedNetwork,
            unexpectedRef=unexpectedRef,
        )
    )
