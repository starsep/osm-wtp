import unittest

from configuration import MISSING_REF
from distance import geoDistance, GeoPoint
from warsaw.wtpScraper import lastStopRef, mapWtpStop


class OSMWTPCompareTests(unittest.TestCase):
    def test_mapWtpStop(self):
        self.assertEqual(mapWtpStop("100081", "Test 81"), ("100001", "Test 01"))


class LastStopRefTests(unittest.TestCase):
    def test_lastStopRef(self):
        self.assertEqual(lastStopRef("Nowa 01", "170201"), "199801")
        self.assertEqual(lastStopRef("Bródno-Podgrodzie 08", ""), "115208")
        self.assertEqual(lastStopRef("Example", ""), MISSING_REF)


class GeoDistanceTests(unittest.TestCase):
    def test_geoDistance(self):
        self.assertAlmostEqual(
            geoDistance(
                GeoPoint(lat=52.137859, lon=21.234539),
                GeoPoint(lat=52.136611, lon=21.234386),
            ),
            139,
        )
        self.assertAlmostEqual(
            geoDistance(
                GeoPoint(lat=52.217726, lon=21.242986),
                GeoPoint(lat=52.198978, lon=21.168815),
            ),
            5482,
            delta=20,
        )
