from typing import Dict, List, cast
from urllib import parse

import httpx


def fetchWebsite(link: str) -> str:
    return httpx.get(link, follow_redirects=True).text


def parseLinkArguments(link: str) -> Dict[str, List[str]]:
    return cast(dict[str, List[str]], parse.parse_qs(parse.urlparse(link).query))
