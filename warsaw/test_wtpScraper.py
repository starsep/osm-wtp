from model.stopData import StopData
from warsaw.wtpScraper import mapWtpStop


def test_mapWtpStop():
    assert mapWtpStop(StopData(ref="100081", name="Test 81")) == StopData(
        ref="100001", name="Test 01"
    )
    assert mapWtpStop(StopData(ref="290900", name="Warszawa Falenica")) == StopData(
        ref="290900", name="Warszawa Falenica"
    )
