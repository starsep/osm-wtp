from dataclasses import dataclass

from starsep_utils import Relation
from warsaw.wtpScraper import WTPResult


@dataclass(frozen=True)
class ScrapedOSMRoute:
    route: Relation
    wtpResult: WTPResult
    routeRef: str
    link: str
