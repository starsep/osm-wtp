import re
from dataclasses import dataclass
from itertools import groupby
from typing import Dict, Tuple, List

import logger
from logger import log_duration
from configuration import MISSING_REF
from model.stopData import StopData
from model.types import StopName, StopRef
from warsaw.scrapedOSMRoute import ScrapedOSMRoute


@dataclass(frozen=True)
class LastStopRefsResult:
    lastStopsRefsAfter: Dict[Tuple[str, str], str]
    uniqueRefForName: Dict[str, str]


stopNameRegex = re.compile(r"^(.*) (\d\d)$")


def lastStopRef(
    lastStopName: StopName, previousRef: StopRef, lastStopRefsResult: LastStopRefsResult
) -> str:
    match = re.match(stopNameRegex, lastStopName)
    if match is None:
        return MISSING_REF
    lastStopGroupName = match.group(1)
    lastStopLocalRef = match.group(2)
    previousGroupRef = previousRef[:4]
    key = (lastStopGroupName, previousGroupRef)
    if lastStopGroupName in lastStopRefsResult.uniqueRefForName:
        return f"{lastStopRefsResult.uniqueRefForName[lastStopGroupName]}{lastStopLocalRef}"
    elif key in lastStopRefsResult.lastStopsRefsAfter:
        return f"{lastStopRefsResult.lastStopsRefsAfter[key]}{lastStopLocalRef}"
    else:
        logger.error(
            f"Couldn't find ref for last stop {lastStopName} after {previousRef}"
        )
        return MISSING_REF


@log_duration
def generateLastStopRefs(scrapedRoutes: List[ScrapedOSMRoute]) -> LastStopRefsResult:
    lastStopsRefsAfter: Dict[Tuple[str, str], str] = dict()

    def addAdjacentStop(adjacentStop: StopData):
        if adjacentStop.ref == MISSING_REF or currentStopGroupRef == MISSING_REF:
            return
        adjacentStopGroupRef = adjacentStop.ref[:4]
        resultKey = (currentStopGroupName, adjacentStopGroupRef)
        if (
            resultKey in lastStopsRefsAfter
            and lastStopsRefsAfter[resultKey] != currentStopGroupRef
        ):
            logger.error(
                f"LastStopRefs conflict for key={resultKey}. Refs {lastStopsRefsAfter[resultKey]} vs {currentStopGroupRef}"
            )
        lastStopsRefsAfter[resultKey] = currentStopGroupRef

    for route in scrapedRoutes:
        stops = route.wtpResult.stops
        stopsCount = len(stops)
        for i in range(stopsCount):
            previousStop = stops[i - 1] if i > 0 else None
            currentStop = stops[i]
            nextStop = stops[i + 1] if i < stopsCount - 1 else None
            currentStopGroupName = " ".join(currentStop.name.split(" ")[:-1])
            currentStopGroupRef = currentStop.ref[:4]
            if previousStop is not None:
                addAdjacentStop(previousStop)
            if nextStop is not None:
                addAdjacentStop(nextStop)
    # Stop Zgoda 01 in Piaseczno is the only case where a stop group has only lines ending in it
    uniqueRefForName: Dict[str, str] = dict(Zgoda=3701)
    for stopGroupName, nameRefTuples in groupby(
        lastStopsRefsAfter.keys(), lambda key: key[0]
    ):
        refsForStopGroupName = set(
            lastStopsRefsAfter[nameRefTuple] for nameRefTuple in nameRefTuples
        )
        if len(refsForStopGroupName) == 1:
            uniqueRefForName[stopGroupName] = list(refsForStopGroupName)[0]
            for nameRefTuple in nameRefTuples:
                del lastStopsRefsAfter[nameRefTuple]
    return LastStopRefsResult(
        lastStopsRefsAfter=lastStopsRefsAfter,
        uniqueRefForName=uniqueRefForName,
    )
