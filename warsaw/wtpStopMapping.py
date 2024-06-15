from typing import Dict

from model.stopData import StopData

# WTP Stop => Actual Stop
wtpStopMapping: Dict[StopData, StopData] = {
    StopData(ref="512002", name="Kolejowa 02"): StopData(
        ref="512052", name="Kolejowa 52"
    ),
    # Lines: 120, 314, N14
    StopData(ref="129301", name="Kobiałka-Szkoła 01"): StopData(
        ref="129351", name="Kobiałka-Szkoła 51"
    ),
    # Lines: 116, 161, 164, 519, 522, N31, N81
    StopData(ref="304202", name="Sobieskiego 02"): StopData(
        ref="304252", name="Sobieskiego 52"
    ),
    StopData(ref="304203", name="Sobieskiego 03"): StopData(
        ref="304253", name="Sobieskiego 53"
    ),
    StopData(ref="304204", name="Sobieskiego 04"): StopData(
        ref="304254", name="Sobieskiego 54"
    ),
    StopData(ref="303001", name="Tor Stegny 01"): StopData(
        ref="303051", name="Tor Stegny 51"
    ),
    StopData(ref="303002", name="Tor Stegny 02"): StopData(
        ref="303052", name="Tor Stegny 52"
    ),
    StopData(ref="703702", name="pl.Na Rozdrożu 02"): StopData(
        ref="703752", name="Pl. Na Rozdrożu 52"
    ),
}
