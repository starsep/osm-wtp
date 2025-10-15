from urllib import parse

from httpx import Client


def fetchWebsite(link: str, httpClient: Client) -> str:
    return httpClient.get(link, follow_redirects=True).text


def parseLinkArguments(link: str) -> dict[str, list[str]]:
    return parse.parse_qs(parse.urlparse(link).query)
