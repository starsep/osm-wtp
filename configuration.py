from pathlib import Path

from diskcache import Cache

MISSING_REF = "-"
cacheDirectory = Path("cache")
cacheOverpass = Cache(str(cacheDirectory / "overpass"))
OVERPASS_URL = None  # "http://localhost:12345/api/interpreter"
WARSAW_ID = 336075
WARSAW_PUBLIC_TRANSPORT_ID = 3652280
