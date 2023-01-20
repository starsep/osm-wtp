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
