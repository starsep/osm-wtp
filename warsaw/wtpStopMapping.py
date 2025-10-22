from model.stopData import StopData

# WTP Stop => Actual Stop
wtpStopMapping: dict[StopData, StopData] = {
    # Example:
    # StopData(ref="512002", name="Kolejowa 02"): StopData(ref="512052", name="Kolejowa 52"),
}
