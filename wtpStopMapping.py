from typing import Dict, Tuple

# (stopRefWTP, stopNameWTP) => (actualStopRef, actualStopName)
wtpStopMapping: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("512002", "Kolejowa 02"): ("512052", "Kolejowa 52"),
    ("107002", "Kamienna 02"): ("107052", "Kamienna 52"),
}
