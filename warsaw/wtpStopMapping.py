from typing import Dict, Tuple

from model.types import StopRef, StopName

# (stopRefWTP, stopNameWTP) => (actualStopRef, actualStopName)
wtpStopMapping: Dict[Tuple[StopRef, StopName], Tuple[StopRef, StopName]] = {
    ("512002", "Kolejowa 02"): ("512052", "Kolejowa 52"),
    ("107002", "Kamienna 02"): ("107052", "Kamienna 52"),
    ("335302", "Oś Królewska 02"): ("335352", "Oś Królewska 52"),  # line 379
    # Lines: 120, 314, N14
    ("129301", "Kobiałka-Szkoła 01"): ("129351", "Kobiałka-Szkoła 51"),
    # Lines: 116, 161, 164, 519, 522, N31, N81 
    ("304201", "Sobieskiego 01"): ("304251", "Sobieskiego 51"),
    ("304202", "Sobieskiego 02"): ("304252", "Sobieskiego 52"),
    ("304203", "Sobieskiego 03"): ("304253", "Sobieskiego 53"),
    ("304204", "Sobieskiego 04"): ("304254", "Sobieskiego 54"),
    ("305802", "Sielce 02"): ("305852", "Sielce 52"),
}
