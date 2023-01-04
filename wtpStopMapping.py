from typing import Dict, Tuple

# (stopRefWTP, stopNameWTP) => (actualStopRef, actualStopName)
wtpStopMapping: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("115383", "Łojewska 83"): ("115303", "Łojewska 03"),
    ("115481", "Klub Lira 81"): ("115401", "Klub Lira 01"),
    ("512002", "Kolejowa 02"): ("512052", "Kolejowa 52"),
    ("107002", "Kamienna 02"): ("107052", "Kamienna 52"),
}
