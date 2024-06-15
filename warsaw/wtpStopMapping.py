from typing import Dict, Tuple

from model.types import StopRef, StopName

# (stopRefWTP, stopNameWTP) => (actualStopRef, actualStopName)
wtpStopMapping: Dict[Tuple[StopRef, StopName], Tuple[StopRef, StopName]] = {
    ("512002", "Kolejowa 02"): ("512052", "Kolejowa 52"),
    # Lines: 120, 314, N14
    ("129301", "Kobiałka-Szkoła 01"): ("129351", "Kobiałka-Szkoła 51"),
    # Lines: 116, 161, 164, 519, 522, N31, N81
    ("304202", "Sobieskiego 02"): ("304252", "Sobieskiego 52"),
    ("304203", "Sobieskiego 03"): ("304253", "Sobieskiego 53"),
    ("304204", "Sobieskiego 04"): ("304254", "Sobieskiego 54"),
    ("303001", "Tor Stegny 01"): ("303051", "Tor Stegny 51"),
    ("303002", "Tor Stegny 02"): ("303052", "Tor Stegny 52"),
    ("703702", "pl.Na Rozdrożu 02"): ("703752", "Pl. Na Rozdrożu 52"),
}
