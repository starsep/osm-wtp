import unittest

from distance import geoDistance, GeoPoint
from model.stopData import StopData
from warsaw.wtpScraper import mapWtpStop


class OSMWTPCompareTests(unittest.TestCase):
    def test_mapWtpStop(self):
        self.assertEqual(
            mapWtpStop(StopData(ref="100081", name="Test 81")),
            StopData(ref="100001", name="Test 01"),
        )


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
