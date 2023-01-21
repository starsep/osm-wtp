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
    missingRef,
    allOSMRefs,
    unexpectedLink,
    unexpectedNetwork,
    unexpectedRef,
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
                refs=compareResults.refs,
                startTime=startTime.isoformat(timespec="seconds"),
                generationSeconds=generationSeconds,
                renderResults=compareResults.renderResults,
                disusedStop=disusedStop,
                invalidWtpVariants=invalidOperatorVariants,
                wtpManyLastStops=manyLastStops,
                notUniqueOSMNames={
                    ref: names for ref, names in osmRefToName.items() if len(names) > 1
                },
                notUniqueWTPNames={
                    ref: names
                    for ref, names in compareResults.operatorRefToName.items()
                    if len(names) > 1
                },
                mismatchOSMNameRef=mismatchOSMNameRef,
                wtpMissingLastStop=wtpMissingLastStop,
                missingLastStopRefNames=list(sorted(wtpMissingLastStopRefNames)),
                missingName=missingName,
                missingRouteUrl=missingRouteUrl,
                missingRef=missingRef,
                missingRefsInOSM=[
                    (ref, list(compareResults.operatorRefToName[ref])[0])
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
