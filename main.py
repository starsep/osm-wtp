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
from tqdm import tqdm

from configuration import OVERPASS_URL, WARSAW_ID, cacheOverpass, cacheWTP

overpassApi = overpy.Overpass(url=OVERPASS_URL)
startTime = datetime.now()


@cacheOverpass.memoize()
def getRelationDataFromOverpass():
    areaId = 3600000000 + WARSAW_ID
    query = f"""
    [out:json][timeout:250];
    (
        relation(area:{areaId})[route][network="ZTM Warszawa"][url];
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


printedMissingRefName = set()

for route in tqdm(getRelationDataFromOverpass().relations):
    wtpStops = []
    tags = route.tags
    ref = tags["ref"]
    if "type" not in tags or "route" not in tags or tags["type"] != "route":
        continue
    if "url" not in tags:
        print(f"Missing url tag for {route}")
        continue
    link = tags["url"]
    if "wtp.waw.pl" not in link:
        print(f"Unexpected link {link} for {route}")
        continue
    content = BeautifulSoup(fetchWtpWebsite(link), features="html.parser")
    for stopLink in content.select("a.timetable-link.active"):
        stopName = stopLink.text.strip()
        stopLink = stopLink.get("href")
        stopLinkArgs = parse.parse_qs(parse.urlparse(stopLink).query)
        stopRef = stopLinkArgs["wtp_st"][0] + stopLinkArgs["wtp_pt"][0]
        wtpStops.append(StopData(name=stopName, ref=stopRef))
    lastStop = content.select("div.timetable-route-point.name.active.follow.disabled")
    if len(lastStop) != 1:
        print(f"Unexpected number of last stops: {lastStop}. Link: {link}")
        continue
    for stopLink in lastStop:
        stopName = stopLink.text.strip()
        wtpStops.append(StopData(name=stopName, ref=MISSING_REF))
    osmStops = []
    for member in route.members:
        role: str = member.role
        if role.startswith("platform") or role.startswith("stop"):
            element = member.resolve()
            if "name" not in element.tags or "ref" not in element.tags:
                url = elementUrl(element)
                if url not in printedMissingRefName:
                    print(f"Missing name or ref for {url}")
                    printedMissingRefName.add(url)
                continue
            if len(element.tags["ref"]) != 6:
                if "network" in element.tags and element.tags["network"] == "ZTM Warszawa":
                    print(f"Bad ref={element.tags['ref']} format for {elementUrl(element)}")
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

with Path("../osm-wtp/index.html").open("w") as f:

    def writeLine(line: str):
        f.write(line + "\n")

    refs = sorted(results.keys(), key=lambda x: (len(x), x))
    for ref in refs:
        writeLine(f"<a href='#{ref}'>{ref}</a>")
    for ref in refs:
        writeLine(f"<h1 id='{ref}'>Wyniki dla {ref}</h1>")
        success = True
        for route in results[ref]:
            osmRefs = [stop.ref for stop in route.osmStops]
            wtpRefs = [stop.ref for stop in route.wtpStops]
            osmNames = {stop.ref: stop.name for stop in route.osmStops}
            wtpNames = {stop.ref: stop.name for stop in route.wtpStops}
            if osmRefs[:-1] != wtpRefs[:-1]:
                writeLine(
                    f"""
                    <h3>
                        Błąd dla {route.osmName}:
                        <a href="{route.wtpLink}">WTP</a>
                        <a href="https://osm.org/relation/{route.osmId}">OSM</a>
                        <a target="hiddenIframe" href="http://127.0.0.1:8111/load_object?new_layer=false&relation_members=true&objects=r{route.osmId}">JOSM</a>
                    </h3>
                """
                )
                writeLine("<table>")
                writeLine(
                    f"<thead><tr><th>OSM ref</th><th>OSM name</th><th>WTP ref</th><th>WTP name</th></thead>"
                )
                matcher = SequenceMatcher(None, osmRefs, wtpRefs)

                def writeTableRow(refOSM: str, refOperator: str):
                    nameOSM = osmNames[refOSM] if refOSM != MISSING_REF else MISSING_REF
                    nameOperator = (
                        wtpNames[refOperator]
                        if refOperator != MISSING_REF
                        else MISSING_REF
                    )
                    if refOSM == osmRefs[-1] and refOperator == MISSING_REF:
                        nameOperator = wtpNames[wtpRefs[-1]]
                    style = ""
                    if refOSM == refOperator:
                        style = ""
                    elif refOSM == MISSING_REF:
                        style = "color: green;"
                    elif refOSM != MISSING_REF and refOperator != MISSING_REF:
                        style = "color: orange;"
                    elif refOperator == MISSING_REF and nameOperator == MISSING_REF:
                        style = "color: red;"
                    elif refOperator == MISSING_REF and nameOperator != MISSING_REF:
                        style = "color: orange;" if nameOSM != nameOperator else ""
                    writeLine(
                        f"<tr style='{style}'><td>{refOSM}</td><td>{nameOSM}</td><td>{refOperator}</td><td>{nameOperator}</td>"
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
                writeLine("</table>")
                writeLine("<br/>")
                success = False
        if success:
            writeLine("Wszystko ok!\n")
    endTime = datetime.now()
    generationSeconds = int((endTime - startTime).total_seconds())
    writeLine(f"Początek generowania: {startTime.isoformat(timespec='seconds')}. Zajęło {generationSeconds} sekund")
    writeLine(
        '<iframe style="display:none" id="hiddenIframe" name="hiddenIframe"></iframe>'
    )
