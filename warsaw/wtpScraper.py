import re
from dataclasses import dataclass
from typing import Optional, Tuple, List, Set
from urllib import parse

from bs4 import BeautifulSoup

import logger
from logger import log_duration
from configuration import MISSING_REF
from model.types import StopName, StopRef
from warsaw.wtpLastStopRefs import lastStopRefs, lastStopRefAfter
from model.stopData import StopData
from scraper.scraper import cache, parseLinkArguments, fetchWebsite
from warsaw.wtpStopMapping import wtpStopMapping

lineNotAvailableToday = "Najbliższy dzień z dostępnym rozkładem dla wybranej linii to"
lineNotAvailableTodayPattern = (
    f'div.timetable-message:-soup-contains("{lineNotAvailableToday}")'
)
variantNotAvailable = (
    "Wybrany wariant trasy jest niedostępny dla określonego kierunku linii"
)


wtpModeArg = "wtp_md"
wtpLineArg = "wtp_ln"
wtpDirectionArg = "wtp_dr"
wtpVariantArg = "wtp_vr"
wtpDateArg = "wtp_dt"
wtpDomain = "wtp.waw.pl"


wtpCache = cache("WTP")


@dataclass
class WTPLink:
    line: str
    direction: str
    variant: str

    def url(self) -> str:
        return f"https://www.{wtpDomain}/rozklady-jazdy/?{wtpModeArg}=3&{wtpLineArg}={self.line}&{wtpDirectionArg}={self.direction}&{wtpVariantArg}={self.variant}"

    def toTuple(self) -> Tuple[str, str, str]:
        return self.line, self.direction, self.variant

    @staticmethod
    def fromTuple(t: Tuple[str, str, str]) -> "WTPLink":
        (line, direction, variant) = t
        return WTPLink(line=line, direction=direction, variant=variant)

    @staticmethod
    def parseWTPRouteLink(url: str) -> Optional["WTPLink"]:
        args = parse.parse_qs(parse.urlparse(url).query)
        if (
            wtpModeArg not in args
            or args[wtpModeArg][0] != "3"
            or wtpLineArg not in args
        ):
            return None
        return WTPLink(
            line=args[wtpLineArg][0],
            direction=args[wtpDirectionArg][0] if wtpDirectionArg in args else "A",
            variant=args[wtpVariantArg][0] if wtpVariantArg in args else "0",
        )


@dataclass
class WTPResult:
    notAvailable: bool
    detour: bool
    new: bool
    short: bool
    stops: List[StopData]


@dataclass
class CachedWTPResult:
    wtpResult: WTPResult
    stopRefs: Set[str]
    seenLinks: Set[Tuple[str, str, str]]
    missingLastStop: Set[str]
    manyLastStops: Set[Tuple[str, str]]
    missingLastStopRefNames: Set[Tuple[str, str]]


wtpSeenLinks: Set[Tuple[str, str, str]] = set()
wtpStopRefs: Set[str] = set()
wtpMissingLastStop: Set[str] = set()
wtpManyLastStops: Set[Tuple[str, str]] = set()
wtpMissingLastStopRefNames: Set[Tuple[str, str]] = set()


# @wtpCache.memoize()
def cachedScrapeLink(link: str) -> CachedWTPResult:
    htmlContent = fetchWebsite(link)
    return cachedParseWebsite(htmlContent=htmlContent, link=link)


def scrapeLink(link: str) -> WTPResult:
    cachedResult = cachedScrapeLink(link)
    wtpSeenLinks.update(cachedResult.seenLinks)
    wtpStopRefs.update(cachedResult.stopRefs)
    wtpMissingLastStop.update(cachedResult.missingLastStop)
    wtpManyLastStops.update(cachedResult.manyLastStops)
    wtpMissingLastStopRefNames.update(cachedResult.missingLastStopRefNames)
    return cachedResult.wtpResult


def cachedParseWebsite(htmlContent: str, link: str) -> CachedWTPResult:
    parser = BeautifulSoup(htmlContent, features="html.parser")
    stopRefs: Set[str] = set()
    seenLinks: Set[Tuple[str, str, str]] = set()
    missingLastStop: Set[str] = set()
    manyLastStops: Set[Tuple[str, str]] = set()
    missingLastStopRefNames: Set[Tuple[str, str]] = set()
    if variantNotAvailable in htmlContent:
        return CachedWTPResult(
            wtpResult=WTPResult(
                notAvailable=True, detour=False, new=False, short=False, stops=[]
            ),
            stopRefs=stopRefs,
            seenLinks=seenLinks,
            missingLastStop=missingLastStop,
            manyLastStops=manyLastStops,
            missingLastStopRefNames=missingLastStopRefNames,
        )
    notAvailableDiv = parser.select(lineNotAvailableTodayPattern)
    if len(notAvailableDiv) > 0:
        anotherDateLink = notAvailableDiv[0].select("a")[0].get("href")
        anotherDateLinkArgs = parseLinkArguments(anotherDateLink)
        if wtpDateArg in anotherDateLinkArgs:
            return cachedScrapeLink(
                link + f"&{wtpDateArg}={anotherDateLinkArgs[wtpDateArg][0]}"
            )
    for link in parser.select("a"):
        url = link.get("href")
        if wtpDomain not in url:
            continue
        parsedUrl = WTPLink.parseWTPRouteLink(url)
        if parsedUrl is not None:
            seenLinks.add(parsedUrl.toTuple())
    stops = []
    # handle stops with links
    for stopLink in parser.select("a.timetable-link.active"):
        stopName = stopLink.text.strip()
        stopLink = stopLink.get("href")
        stopLinkArgs = parseLinkArguments(stopLink)
        stopRef = stopLinkArgs["wtp_st"][0] + stopLinkArgs["wtp_pt"][0]
        stopRef, stopName = mapWtpStop(stopRef, stopName)
        stopRefs.add(stopRef)
        stops.append(StopData(name=stopName, ref=stopRef))
    # handle last stop without link
    lastStop = parser.select("div.timetable-route-point.name.active.follow.disabled")
    if len(lastStop) == 0:
        missingLastStop.add(link)
    if len(lastStop) > 1:
        manyLastStops.add((link, str(lastStop)))
    for stopLink in lastStop[:1]:
        stopName = stopLink.text.strip()
        if len(stops) == 0:
            print(f"Error empty stops: {link}")
            continue
        stopRef = lastStopRef(lastStopName=stopName, previousRef=stops[-1].ref)
        if stopRef == MISSING_REF:
            missingLastStopRefNames.add((stopName, stops[-1].ref))
        stopRef, stopName = mapWtpStop(stopRef, stopName)
        stopRefs.add(stopRef)
        stops.append(StopData(name=stopName, ref=stopRef))
    return CachedWTPResult(
        WTPResult(
            notAvailable=False,
            detour=len(parser.select("div.timetable-route-point.active.detour")) > 0,
            new=len(parser.select("div.timetable-route-point.active.new")) > 0,
            short=len(parser.select("div.timetable-route-point.active.short")) > 0,
            stops=stops,
        ),
        stopRefs=stopRefs,
        seenLinks=seenLinks,
        missingLastStop=missingLastStop,
        manyLastStops=manyLastStops,
        missingLastStopRefNames=missingLastStopRefNames,
    )


@wtpCache.memoize()
def cachedScrapeHomepage() -> List[Tuple[str, str, str]]:
    mainContent = BeautifulSoup(
        fetchWebsite(f"https://www.{wtpDomain}/rozklady-jazdy/"), features="html.parser"
    )
    result: List[Tuple[str, str, str]] = []
    for wtpLink in mainContent.select("a"):
        url = wtpLink.get("href")
        if wtpDomain not in url:
            continue
        parsedUrl = WTPLink.parseWTPRouteLink(url)
        if parsedUrl is not None:
            result.append(parsedUrl.toTuple())
    return result


@log_duration
def scrapeHomepage():
    logger.info("🔧 Scraping WTP homepage")
    wtpSeenLinks.update(cachedScrapeHomepage())


stopNameRegex = re.compile(r"^(.*) (\d\d)$")


def lastStopRef(lastStopName: StopName, previousRef: StopRef) -> str:
    match = re.match(stopNameRegex, lastStopName)
    if match is None:
        return MISSING_REF
    lastStopAreaName = match.group(1)
    lastStopLocalRef = match.group(2)
    key = (lastStopAreaName, previousRef)
    if key in lastStopRefAfter:
        return f"{lastStopRefAfter[key]}{lastStopLocalRef}"
    elif lastStopAreaName in lastStopRefs:
        return f"{lastStopRefs[lastStopAreaName]}{lastStopLocalRef}"
    else:
        return MISSING_REF


def mapWtpStop(wtpStopRef: StopRef, wtpStopName: StopName) -> Tuple[StopRef, StopName]:
    key = (wtpStopRef, wtpStopName)
    if (wtpStopRef, wtpStopName) in wtpStopMapping:
        return wtpStopMapping[key]
    # stops 8x => 0x
    if len(wtpStopRef) == 6 and wtpStopRef[-2] == "8":
        return (
            f"{wtpStopRef[:-2]}0{wtpStopRef[-1]}",
            f"{wtpStopName[:-2]}0{wtpStopName[-1]}",
        )
    return key
