OSMError = str


def osmErrorStopsNotWithinRoute() -> OSMError:
    return "Punkty zatrzymania nie należą do trasy"


def osmErrorAccessNo() -> OSMError:
    return "access=no bez bus/psv=yes/designated"


def osmErrorWayWithoutHighwayRailwayTag() -> OSMError:
    return "Trasa przebiega przez element bez tagu highway/railway"


def osmErrorInvalidWayTag(tag: str) -> OSMError:
    return f"Trasa używa {tag}"


def osmErrorUnsplitRoundabout() -> OSMError:
    return "Niepodzielone rondo jest częścią trasy"


def osmErrorStopNotBeingNode() -> OSMError:
    return "Stop niebędący punktem"


def osmErrorElementWithoutRoleWhichIsNotWay() -> OSMError:
    return "Element bez roli niebędący linią"


def osmErrorRouteHasGaps() -> OSMError:
    return "Trasa jest niespójna"


def osmErrorOnewayUsedWrongDirection(wayId: int) -> OSMError:
    return f"Jednokierunkowa droga używana pod prąd {wayId}"
