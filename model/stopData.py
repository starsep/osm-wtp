from dataclasses import dataclass


@dataclass(frozen=True)
class StopData:
    name: str
    ref: str
