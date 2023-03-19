import unittest

from configuration import MISSING_REF
from warsaw.wtpScraper import lastStopRef, mapWtpStop


class OSMWTPCompareTests(unittest.TestCase):
    def test_mapWtpStop(self):
        self.assertEqual(mapWtpStop("100081", "Test 81"), ("100001", "Test 01"))


class LastStopRefTests(unittest.TestCase):
    def test_lastStopRef(self):
        self.assertEqual(lastStopRef("Nowa 01", "170201"), "199801")
        self.assertEqual(lastStopRef("Bródno-Podgrodzie 08", ""), "115208")
        self.assertEqual(lastStopRef("Example", ""), MISSING_REF)
