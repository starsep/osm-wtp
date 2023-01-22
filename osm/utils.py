from typing import Tuple, cast, Optional

import overpy


def elementUrl(element: overpy.Element) -> str:
    if type(element) == overpy.Node:
        return f"https://osm.org/node/{element.id}"
    elif type(element) == overpy.Way:
        return f"https://osm.org/way/{element.id}"
    elif type(element) == overpy.Relation:
        return f"https://osm.org/relation/{element.id}"
    else:
        print(f"Unexpected overpy type: {type(element)}")


def coordinatesOfStop(stop: overpy.Element) -> Optional[Tuple[float, float]]:
    if type(stop) == overpy.Node:
        stop = cast(overpy.Node, stop)
        return float(stop.lat), float(stop.lon)
    elif type(stop) == overpy.Way:
        stop = cast(overpy.Way, stop)
        if stop.center_lat is None or stop.center_lon is None:
            return None
        return float(stop.center_lat), float(stop.center_lon)
    elif type(stop) == overpy.Relation:
        stop = cast(overpy.Relation, stop)
        if stop.center_lat is None or stop.center_lon is None:
            return None
        return float(stop.center_lat), float(stop.center_lon)
    else:
        print(f"Unexpected overpy type: {type(stop)}")
