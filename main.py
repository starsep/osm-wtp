#!/usr/bin/env python3
import logging
from datetime import datetime
from pathlib import Path
from typing import Set

from jinja2 import (
    Environment,
    select_autoescape,
    FileSystemLoader,
    StrictUndefined,
)

from compare.comparator import compareStops
from configuration import MISSING_REF, outputDirectory, ENABLE_TRAIN
from gtfs.osmGTFSStopsComparer import (
    compareOSMAndGTFSStops,
    STOP_DISTANCE_THRESHOLD,
    loadGTFSStops,
)
from osm.OSMRelationAnalyzer import (
    analyzeOSMRelations,
    osmRefToName,
    osmOperatorLinks,
    disusedStop,
    invalidOperatorVariants,
    manyLastStops,
    mismatchOSMNameRefNonRailway,
    mismatchOSMNameRefRailway,
    missingName,
    missingRouteUrl,
    missingStopRef,
    allOSMRefs,
    unexpectedLink,
    unexpectedNetwork,
    unexpectedStopRef,
    wtpLinkDuplicates,
)
from warsaw.fetchApiRoutes import fetchApiRoutes
from warsaw.wtpScraper import (
    WTPLink,
    wtpSeenLinks,
    scrapeHomepage,
    wtpMissingLastStop,
    wtpMissingLastStopRefNames,
    wtpStopRefs,
)
from warsaw.wtpStopMapping import wtpStopMapping
from starsep_utils.healthchecks import healthchecks

startTime = datetime.now()


def processData():
    scrapeHomepage()
    apiResults = fetchApiRoutes()
    gtfsStops = loadGTFSStops()
    osmResults = analyzeOSMRelations(apiResults, gtfsStops)
    # compareApiRoutesWithOSM(apiResults, osmResults)
    compareResults = compareStops(osmResults=osmResults)
    notLinkedWtpUrls: Set[str] = set()
    for link in wtpSeenLinks - osmOperatorLinks:
        wtpLinkParams = WTPLink.fromTuple(link)
        if wtpLinkParams.line not in ["M1", "M2"] or (
            not ENABLE_TRAIN and not wtpLinkParams.line.startswith("S")
        ):
            notLinkedWtpUrls.add(wtpLinkParams.url())
    osmAndGTFSComparisonResult = compareOSMAndGTFSStops(gtfsStops)
    env = Environment(
        loader=FileSystemLoader(searchpath="./templates"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    endTime = datetime.now()
    generationSeconds = int((endTime - startTime).total_seconds())
    sharedContext = dict(
        startTime=startTime.isoformat(timespec="seconds"),
        generationSeconds=generationSeconds,
    )
    with Path(outputDirectory, "index.html").open("w") as f:
        template = env.get_template("index.j2")
        f.write(
            template.render(
                refs=compareResults.refs,
                renderResults=compareResults.renderResults,
                disusedStop=disusedStop,
                invalidWtpVariants=invalidOperatorVariants,
                wtpManyLastStops=manyLastStops,
                wtpMissingLastStop=wtpMissingLastStop,
                missingRouteUrl=missingRouteUrl,
                notLinkedWtpUrls=sorted(list(notLinkedWtpUrls)),
                unexpectedLink=unexpectedLink,
                unexpectedNetwork=unexpectedNetwork,
                wtpLinkDuplicates=wtpLinkDuplicates,
                ENABLE_TRAIN=ENABLE_TRAIN,
                **sharedContext,
            )
        )
    with Path(outputDirectory, "stops.html").open("w") as f:
        template = env.get_template("stops.j2")
        f.write(
            template.render(
                farAwayStops=osmAndGTFSComparisonResult.farAwayStops,
                stopDistanceThreshold=int(STOP_DISTANCE_THRESHOLD),
                notUniqueOSMNames={
                    ref: names for ref, names in osmRefToName.items() if len(names) > 1
                },
                notUniqueWTPNames={
                    ref: names
                    for ref, names in compareResults.operatorRefToName.items()
                    if len(names) > 1
                },
                mismatchOSMNameRefRailway=sorted(list(mismatchOSMNameRefRailway)),
                mismatchOSMNameRefNonRailway=sorted(list(mismatchOSMNameRefNonRailway)),
                missingLastStopRefNames=sorted(list(wtpMissingLastStopRefNames)),
                missingName=missingName,
                missingStopRef=missingStopRef,
                missingRefsInOSM=[
                    (ref, list(compareResults.operatorRefToName[ref])[0])
                    for ref in sorted(wtpStopRefs - allOSMRefs - set(MISSING_REF))
                ],
                unexpectedStopRef=unexpectedStopRef,
                wtpStopMapping=wtpStopMapping,
                osmStops=osmAndGTFSComparisonResult.osmStops,
                gtfsStops=osmAndGTFSComparisonResult.gtfsStops,
                osmStopRefsNotInGTFS=osmAndGTFSComparisonResult.osmStopRefsNotInGTFS,
                gtfsStopRefsNotInOSM=osmAndGTFSComparisonResult.gtfsStopRefsNotInOSM,
                **sharedContext,
            )
        )


if __name__ == "__main__":
    healthchecks("/start")
    logging.info("🎬 Starting osm-wtp")
    processData()
    healthchecks()
