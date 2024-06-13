from pathlib import Path

import httpx

MISSING_REF = "-"
cacheDirectory = Path("cache")
outputDirectory = Path("osm-wtp")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"  # "http://localhost:12345/api/interpreter"
EXPIRE_WTP_SECONDS = 60 * 60 * 12
ENABLE_TRAIN = True

httpxTimeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=60.0)
