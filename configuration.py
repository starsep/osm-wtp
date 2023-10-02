from pathlib import Path


MISSING_REF = "-"
cacheDirectory = Path("cache")
outputDirectory = Path("osm-wtp")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"  # "http://localhost:12345/api/interpreter"
EXPIRE_WTP_SECONDS = 60 * 60 * 12
ENABLE_TRAIN = True
