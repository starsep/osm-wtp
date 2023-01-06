import unittest

from main import mapWtpStop


class OSMWTPCompareTests(unittest.TestCase):
    def test_mapWtpStop(self):
        self.assertEqual(mapWtpStop("100081", "Test 81"), ("100001", "Test 01"))
