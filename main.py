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
from gtfs.osmGTFSStopsComparer import compareOSMAndGTFSStops, STOP_DISTANCE_THRESHOLD
from osm.OSMRelationAnalyzer import (
    analyzeOSMRelations,
    osmRefToName,
    osmOperatorLinks,
    disusedStop,
    invalidOperatorVariants,
    manyLastStops,
    mismatchOSMNameRef,
    missingName,
    missingRouteUrl,
    missingStopRef,
    allOSMRefs,
    unexpectedLink,
    unexpectedNetwork,
    unexpectedStopRef,
    wtpLinkDuplicates,
)
from warsaw.wtpScraper import (
    WTPLink,
    wtpSeenLinks,
    scrapeHomepage,
    wtpMissingLastStop,
    wtpMissingLastStopRefNames,
    wtpStopRefs,
)
from warsaw.wtpStopMapping import wtpStopMapping

startTime = datetime.now()


def processData():
    scrapeHomepage()
    osmResults = analyzeOSMRelations()
    compareResults = compareStops(osmResults=osmResults)
    notLinkedWtpUrls: Set[str] = set()
    for link in wtpSeenLinks - osmOperatorLinks:
        wtpLinkParams = WTPLink.fromTuple(link)
        if wtpLinkParams.line not in ["M1", "M2"]:
            notLinkedWtpUrls.add(wtpLinkParams.url())
    osmAndGTFSComparisonResult = compareOSMAndGTFSStops()
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
    with Path("osm-wtp/index.html").open("w") as f:
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
                **sharedContext
            )
        )
    with Path("osm-wtp/stops.html").open("w") as f:
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
                mismatchOSMNameRef=mismatchOSMNameRef,
                missingLastStopRefNames=list(sorted(wtpMissingLastStopRefNames)),
                missingName=missingName,
                missingStopRef=missingStopRef,
                missingRefsInOSM=[
                    (ref, list(compareResults.operatorRefToName[ref])[0])
                    for ref in sorted(wtpStopRefs - allOSMRefs)
                ],
                unexpectedStopRef=unexpectedStopRef,
                wtpStopMapping=wtpStopMapping,
                osmStops=osmAndGTFSComparisonResult.osmStops,
                gtfsStops=osmAndGTFSComparisonResult.gtfsStops,
                osmStopRefsNotInGTFS=osmAndGTFSComparisonResult.osmStopRefsNotInGTFS,
                gtfsStopRefsNotInOSM=osmAndGTFSComparisonResult.gtfsStopRefsNotInOSM,
                **sharedContext
            )
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting osm-wtp-compare")
    processData()
