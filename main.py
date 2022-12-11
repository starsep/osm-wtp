from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import List, Dict
from urllib import parse

import httpx
import overpy
from bs4 import BeautifulSoup
from tqdm import tqdm

from configuration import OVERPASS_URL, WARSAW_ID, cache

overpassApi = overpy.Overpass(url=OVERPASS_URL)


@cache.memoize()
def getRelationDataFromOverpass():
    areaId = 3600000000 + WARSAW_ID
    query = f"""
    [out:json][timeout:250];
    (
        relation(area:{areaId})[route=bus][network="ZTM Warszawa"][url];
        relation(area:{areaId})[route=bus][network="ZTM Warszawa"][website];
    );
    (._;>>;);
    out body;
    """
    return overpassApi.query(query)


@cache.memoize()
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

for route in tqdm(getRelationDataFromOverpass().relations):
    wtpStops = []
    tags = route.tags
    ref = tags["ref"]
    if "type" not in tags or "route" not in tags or tags["type"] != "route":
        continue
    if "url" not in tags and "website" not in tags:
        print(f"Missing url/website tag for {route}")
        continue
    link = tags["website"] if "website" in tags else tags["url"]
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
    osmStops = []
    for member in route.members:
        role: str = member.role
        if role.startswith("platform") or role.startswith("stop"):
            element = member.resolve()
            if "name" not in element.tags or "ref" not in element.tags:
                print(f"Missing name or ref for {element}")
                continue
            stop = StopData(name=element.tags["name"], ref=element.tags["ref"])
            if len(osmStops) == 0 or osmStops[-1] != stop:
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

    refs = sorted(results.keys())
    for ref in refs:
        writeLine(f"<a href='#{ref}'>{ref}</a>")
    for ref in refs:
        writeLine(f"<h1 id='{ref}'>Wyniki dla {ref}</h1>")
        success = True
        for route in results[ref]:
            osmRefs = [stop.ref for stop in route.osmStops]
            wtpRefs = [stop.ref for stop in route.wtpStops]
            osmNames = [stop.name for stop in route.osmStops]
            wtpNames = [stop.name for stop in route.wtpStops]
            if osmRefs[:-1] != wtpRefs:
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
                for ((refOSM, nameOSM), (refOperator, nameOperator)) in zip_longest(
                    zip(osmRefs, osmNames),
                    zip(wtpRefs, wtpNames),
                    fillvalue=("-", "-"),
                ):
                    errorStyle = ' style="color:red;"' if refOSM != refOperator else ""
                    writeLine(
                        f"<tr{errorStyle}><td>{refOSM}</td><td>{nameOSM}</td><td>{refOperator}</td><td>{nameOperator}</td>"
                    )
                writeLine("</table>")
                writeLine("<br/>")
                success = False
        if success:
            writeLine("Wszystko ok!\n")
    writeLine(
        '<iframe style="display:none" id="hiddenIframe" name="hiddenIframe"></iframe>'
    )
