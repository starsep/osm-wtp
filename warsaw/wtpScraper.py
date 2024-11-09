import dataclasses
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List, Set
from urllib import parse

import httpx
from bs4 import BeautifulSoup
from diskcache import Cache
from httpx import Client

from starsep_utils import logDuration
from configuration import MISSING_REF, cacheDirectory, EXPIRE_WTP_SECONDS, httpxTimeout
from model.stopData import StopData
from scraper.scraper import parseLinkArguments, fetchWebsite
from warsaw.wtpStopMapping import wtpStopMapping

lineUnavailableToday = "Najbliższy dzień z dostępnym rozkładem dla wybranej linii to"
lineUnavailableTodayPattern = (
    f'div.timetable-message:-soup-contains("{lineUnavailableToday}")'
)
variantUnavailable = (
    "Wybrany wariant trasy jest niedostępny dla określonego kierunku linii"
)
lineUnavailable = "Wybrana linia nie została znaleziona"


wtpModeArg = "wtp_md"
wtpLineArg = "wtp_ln"
wtpDirectionArg = "wtp_dr"
wtpVariantArg = "wtp_vr"
wtpDateArg = "wtp_dt"
wtpDomain = "wtp.waw.pl"

wtpCache = Cache(cacheDirectory / "WTP")


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class WTPResult:
    unavailable: bool
    detour: bool
    new: bool
    short: bool
    stops: List[StopData]
    stopsDetour: List[bool]
    stopsNew: List[bool]


@dataclass(frozen=True)
class CachedWTPResult:
    wtpResult: WTPResult
    seenLinks: Set[Tuple[str, str, str]]
    missingLastStop: Set[str]
    manyLastStops: Set[Tuple[str, str]]
    missingLastStopRefNames: Set[Tuple[str, str]]


wtpSeenLinks: Set[Tuple[str, str, str]] = set()
wtpStopRefs: Set[str] = set()
wtpMissingLastStop: Set[str] = set()
wtpManyLastStops: Set[Tuple[str, str]] = set()
wtpMissingLastStopRefNames: Set[Tuple[str, str]] = set()


@wtpCache.memoize(expire=EXPIRE_WTP_SECONDS, ignore={"httpClient"})
def cachedScrapeLink(link: str, httpClient: Client) -> CachedWTPResult:
    htmlContent = fetchWebsite(link, httpClient=httpClient)
    return cachedParseWebsite(
        htmlContent=htmlContent, inputUrl=link, httpClient=httpClient
    )


def scrapeLink(link: str, httpClient: Client) -> Optional[WTPResult]:
    parsedLink = WTPLink.parseWTPRouteLink(link)
    if parsedLink is None:
        logging.error(f"Couldn't parse link {link}")
        return None
    cachedResult = mapWtpResult(
        cachedScrapeLink(parsedLink.url(), httpClient=httpClient)
    )
    wtpSeenLinks.update(cachedResult.seenLinks)
    wtpStopRefs.update({stop.ref for stop in cachedResult.wtpResult.stops})
    wtpMissingLastStop.update(cachedResult.missingLastStop)
    wtpManyLastStops.update(cachedResult.manyLastStops)
    wtpMissingLastStopRefNames.update(cachedResult.missingLastStopRefNames)
    return cachedResult.wtpResult


def cachedParseWebsite(
    htmlContent: str, inputUrl: str, httpClient: Client
) -> CachedWTPResult:
    parser = BeautifulSoup(htmlContent, features="html.parser")
    seenLinks: Set[Tuple[str, str, str]] = set()
    missingLastStop: Set[str] = set()
    manyLastStops: Set[Tuple[str, str]] = set()
    missingLastStopRefNames: Set[Tuple[str, str]] = set()
    if variantUnavailable in htmlContent or lineUnavailable in htmlContent:
        return CachedWTPResult(
            wtpResult=WTPResult(
                unavailable=True,
                detour=False,
                new=False,
                short=False,
                stops=[],
                stopsDetour=[],
                stopsNew=[],
            ),
            seenLinks=seenLinks,
            missingLastStop=missingLastStop,
            manyLastStops=manyLastStops,
            missingLastStopRefNames=missingLastStopRefNames,
        )
    unavailableDiv = parser.select(lineUnavailableTodayPattern)
    if len(unavailableDiv) > 0:
        anotherDateLink = unavailableDiv[0].select("a")[0].get("href")
        anotherDateLinkArgs = parseLinkArguments(anotherDateLink)
        if wtpDateArg in anotherDateLinkArgs:
            return cachedScrapeLink(
                inputUrl + f"&{wtpDateArg}={anotherDateLinkArgs[wtpDateArg][0]}",
                httpClient=httpClient,
            )
    for link in parser.select("a"):
        url = link.get("href")
        if wtpDomain not in url:
            continue
        parsedUrl = WTPLink.parseWTPRouteLink(url)
        if parsedUrl is not None:
            seenLinks.add(parsedUrl.toTuple())
    stops = []
    stopsDetour: list[bool] = []
    stopsNew: list[bool] = []
    # handle stops with links
    for stopLink in parser.select("a.timetable-link.active"):
        parent = stopLink.parent
        stopName = stopLink.text.strip()
        stopLinkUrl = stopLink.get("href")
        stopLinkArgs = parseLinkArguments(stopLinkUrl)
        stopRef = stopLinkArgs["wtp_st"][0] + stopLinkArgs["wtp_pt"][0]
        stops.append(StopData(name=stopName, ref=stopRef))
        stopsDetour.append(len(parent.select(".detour")) > 0)
        stopsNew.append(len(parent.select(".new")) > 0)
    # handle last stop without link
    lastStop = parser.select("div.timetable-route-point.name.active.follow.disabled")
    if len(lastStop) == 0:
        missingLastStop.add(inputUrl)
    if len(lastStop) > 1:
        manyLastStops.add((inputUrl, str(lastStop)))
    for stopLink in lastStop[:1]:
        stopName = stopLink.text.strip()
        if len(stops) == 0:
            logging.error(f"Empty stops: {inputUrl}")
            continue
        stopRef = MISSING_REF
        stops.append(StopData(name=stopName, ref=stopRef))
        stopsDetour.append(len(stopLink.parent.select(".detour")) > 0)
        stopsNew.append(len(stopLink.parent.select(".new")) > 0)
    return CachedWTPResult(
        WTPResult(
            unavailable=False,
            detour=len(parser.select("div.timetable-route-point.active.detour")) > 0,
            new=len(parser.select("div.timetable-route-point.active.new")) > 0,
            short=len(parser.select("div.timetable-route-point.active.short")) > 0,
            stops=stops,
            stopsNew=stopsNew,
            stopsDetour=stopsDetour,
        ),
        seenLinks=seenLinks,
        missingLastStop=missingLastStop,
        manyLastStops=manyLastStops,
        missingLastStopRefNames=missingLastStopRefNames,
    )


@wtpCache.memoize(expire=EXPIRE_WTP_SECONDS)
def cachedScrapeHomepage() -> List[Tuple[str, str, str]]:
    with httpx.Client(timeout=httpxTimeout) as httpClient:
        mainContent = BeautifulSoup(
            fetchWebsite(
                f"https://www.{wtpDomain}/rozklady-jazdy/", httpClient=httpClient
            ),
            features="html.parser",
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


@logDuration
def scrapeHomepage():
    logging.info("🔧 Scraping WTP homepage")
    wtpSeenLinks.update(cachedScrapeHomepage())


def mapWtpResult(cachedWTPResult: CachedWTPResult) -> CachedWTPResult:
    cachedWTPResult = dataclasses.replace(
        cachedWTPResult,
        wtpResult=dataclasses.replace(
            cachedWTPResult.wtpResult,
            stops=list(map(mapWtpStop, cachedWTPResult.wtpResult.stops)),
        ),
    )
    return cachedWTPResult


def mapWtpStop(wtpStop: StopData) -> StopData:
    if wtpStop in wtpStopMapping:
        return wtpStopMapping[wtpStop]
    # stops 8x => 0x
    if len(wtpStop.ref) == 6 and wtpStop.ref[-2] == "8":
        return StopData(
            ref=f"{wtpStop.ref[:-2]}0{wtpStop.ref[-1]}",
            name=f"{wtpStop.name[:-2]}0{wtpStop.name[-1]}",
        )
    return wtpStop
