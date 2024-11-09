from warsaw.fetchApiRoutes import _parseApiUMData, APIUMWarszawaRouteResult


def _stopFromRef(ref: str):
    return {
        "odleglosc": 1234,
        "ulica_id": "1234",
        "nr_zespolu": ref[:4],
        "typ": "1",
        "nr_przystanku": ref[4:6],
    }


def testParseApiUMData(mocker):
    mocker.patch("starsep_utils.logDuration", lambda x: x)

    routeRef = "123"
    variantId = "TEST"
    expectedRefs = ["100001", "200002", "300003", "999999"]
    exampleData = {
        routeRef: {
            variantId: {
                "1": _stopFromRef(ref=expectedRefs[0]),
                "3": _stopFromRef(ref=expectedRefs[2]),
                "10": _stopFromRef(ref=expectedRefs[3]),
                "2": _stopFromRef(ref=expectedRefs[1]),
            }
        }
    }
    expectedResult = {
        routeRef: [
            APIUMWarszawaRouteResult(
                routeRef=routeRef,
                variantId=variantId,
                stopRefs=expectedRefs,
            )
        ]
    }

    assert _parseApiUMData(exampleData) == expectedResult
