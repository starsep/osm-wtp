from typing import Dict, Tuple

from model.types import StopRef, StopName

# (stopRefWTP, stopNameWTP) => (actualStopRef, actualStopName)
wtpStopMapping: Dict[Tuple[StopRef, StopName], Tuple[StopRef, StopName]] = {
    ("512002", "Kolejowa 02"): ("512052", "Kolejowa 52"),
    ("107002", "Kamienna 02"): ("107052", "Kamienna 52"),
    ("335302", "Oś Królewska 02"): ("335352", "Oś Królewska 52"),  # line 379
}
