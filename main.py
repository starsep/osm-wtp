#!/usr/bin/env -S uv run python
import logging
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    select_autoescape,
)
from starsep_utils.healthchecks import healthchecks

from compare.comparator import compareStops
from configuration import ENABLE_TRAIN, MISSING_REF, outputDirectory
from gtfs.osmGTFSStopsComparer import (
    STOP_DISTANCE_THRESHOLD,
    compareOSMAndGTFSStops,
    loadGTFSStops,
)
from osm.OSMRelationAnalyzer import (
    allOSMRefs,
    analyzeOSMRelations,
    disusedStop,
    invalidOperatorVariants,
    manyLastStops,
    mismatchOSMNameRefNonRailway,
    mismatchOSMNameRefRailway,
    missingName,
    missingRouteUrl,
    missingStopRef,
    osmOperatorLinks,
    osmRefToName,
    unexpectedLink,
    unexpectedNetwork,
    unexpectedStopRef,
    wtpLinkDuplicates,
)
from warsaw.fetchApiRoutes import fetchApiRoutes
from warsaw.wtpScraper import (
    WTPLink,
    scrapeHomepage,
    wtpMissingLastStop,
    wtpMissingLastStopRefNames,
    wtpSeenLinks,
    wtpStopRefs,
)
from warsaw.wtpStopMapping import wtpStopMapping

startTime = datetime.now(UTC)


def processData() -> None:
    scrapeHomepage()
    apiResults = fetchApiRoutes()
    gtfsStops = loadGTFSStops()
    osmResults = analyzeOSMRelations(apiResults, gtfsStops)
    # currently unused: compareApiRoutesWithOSM(apiResults, osmResults)
    compareResults = compareStops(osmResults=osmResults)
    notLinkedWtpUrls: set[str] = set()
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
    endTime = datetime.now(UTC)
    generationSeconds = int((endTime - startTime).total_seconds())
    sharedContext = {
        "startTime": startTime.isoformat(timespec="seconds"),
        "generationSeconds": generationSeconds,
    }
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
                notLinkedWtpUrls=sorted(notLinkedWtpUrls),
                unexpectedLink=unexpectedLink,
                unexpectedNetwork=unexpectedNetwork,
                wtpLinkDuplicates=wtpLinkDuplicates,
                ENABLE_TRAIN=ENABLE_TRAIN,
                **sharedContext,
            ),
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
                mismatchOSMNameRefRailway=sorted(mismatchOSMNameRefRailway),
                mismatchOSMNameRefNonRailway=sorted(mismatchOSMNameRefNonRailway),
                missingLastStopRefNames=sorted(wtpMissingLastStopRefNames),
                missingName=missingName,
                missingStopRef=missingStopRef,
                missingRefsInOSM=[
                    (ref, next(iter(compareResults.operatorRefToName[ref])))
                    for ref in sorted(wtpStopRefs - allOSMRefs - set(MISSING_REF))
                ],
                unexpectedStopRef=unexpectedStopRef,
                wtpStopMapping=wtpStopMapping,
                osmStops=osmAndGTFSComparisonResult.osmStops,
                gtfsStops=osmAndGTFSComparisonResult.gtfsStops,
                osmStopRefsNotInGTFS=osmAndGTFSComparisonResult.osmStopRefsNotInGTFS,
                gtfsStopRefsNotInOSM=osmAndGTFSComparisonResult.gtfsStopRefsNotInOSM,
                **sharedContext,
            ),
        )


if __name__ == "__main__":
    healthchecks("/start")
    logging.info("🎬 Starting osm-wtp")
    processData()
    healthchecks()
