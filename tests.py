import unittest

from model.stopData import StopData
from warsaw.wtpScraper import mapWtpStop


class OSMWTPCompareTests(unittest.TestCase):
    def test_mapWtpStop(self):
        self.assertEqual(
            mapWtpStop(StopData(ref="100081", name="Test 81")),
            StopData(ref="100001", name="Test 01"),
        )
