import httpx

from configuration import httpxTimeout


def httpxClient():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    return httpx.Client(timeout=httpxTimeout, headers=headers)
