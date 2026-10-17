import os
import sys
import unittest
from datetime import datetime

# Add agent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from collectors.datetime_util import collect_datetime_info
from collectors.fbr import FbrChecker
from collectors.printer import is_ignored_printer, clean_copy_suffix, filter_and_deduplicate_printers
from collectors.network import parse_host_and_port, check_dns, get_device_ip_to_gateway

class TestAgentCollectors(unittest.TestCase):

    def test_datetime_collection(self):
        info = collect_datetime_info()
        self.assertIn("local_time", info)
        self.assertIn("utc_time", info)
        self.assertIn("timezone_name", info)
        self.assertIn("utc_offset_minutes", info)
        self.assertIn("uptime_sec", info)
        self.assertGreaterEqual(info["uptime_sec"], 0.0)

        # Verify ISO 8601 parsing
        local_dt = datetime.fromisoformat(info["local_time"])
        self.assertIsNotNone(local_dt.tzinfo)

    def test_fbr_checker_not_configured(self):
        checker = FbrChecker(url="")
        res = checker.check()
        self.assertEqual(res["fbr_status"], "NOT_CONFIGURED")
        self.assertTrue(res["fbr_ok"])
        self.assertEqual(res["consecutive_failures"], 0)

    def test_fbr_checker_placeholder(self):
        checker = FbrChecker(url="PASTE_FBR_URL_HERE")
        res = checker.check()
        self.assertEqual(res["fbr_status"], "NOT_CONFIGURED")

    def test_printer_filtering(self):
        # Ignored printers
        self.assertTrue(is_ignored_printer("Microsoft Print to PDF", "PORTPROMPT:"))
        self.assertTrue(is_ignored_printer("OneNote for Windows 10", "nul:"))
        self.assertTrue(is_ignored_printer("AnyDesk Printer", "AD_Port"))
        self.assertTrue(is_ignored_printer("Fax", "SHRFAX:"))
        self.assertTrue(is_ignored_printer("Receipt", "Microsoft.Office.Port"))

        # Real printers
        self.assertFalse(is_ignored_printer("Epson TM-T88VI Receipt", "USB001"))
        self.assertFalse(is_ignored_printer("Bixolon SRP-350plus", "192.168.1.200:9100"))

    def test_printer_clean_suffix_and_deduplication(self):
        self.assertEqual(clean_copy_suffix("Epson TM-T88 (Copy 1)"), "Epson TM-T88")
        self.assertEqual(clean_copy_suffix("Epson TM-T88 (Copy of 2)"), "Epson TM-T88")

        raw = [
            {"name": "Epson TM-T88", "port": "USB001", "driver": "TM-T88 Driver", "status": "Idle", "queue": 0, "is_offline": False},
            {"name": "Epson TM-T88 (Copy 1)", "port": "USB001", "driver": "TM-T88 Driver", "status": "Idle", "queue": 0, "is_offline": False},
            {"name": "Microsoft Print to PDF", "port": "PORTPROMPT:", "driver": "PDF", "status": "Idle", "queue": 0, "is_offline": False},
            {"name": "Kitchen Bixolon", "port": "192.168.1.201", "driver": "Bixolon", "status": "Printing", "queue": 1, "is_offline": False}
        ]

        filtered = filter_and_deduplicate_printers(raw)
        self.assertEqual(len(filtered), 2)
        names = [p["name"] for p in filtered]
        self.assertIn("Epson TM-T88", names)
        self.assertIn("Kitchen Bixolon", names)

    def test_network_parse_host_and_port(self):
        h, p = parse_host_and_port("http://192.168.1.10:8000")
        self.assertEqual(h, "192.168.1.10")
        self.assertEqual(p, 8000)

        h2, p2 = parse_host_and_port("https://gateway.hbk.internal")
        self.assertEqual(h2, "gateway.hbk.internal")
        self.assertEqual(p2, 443)

if __name__ == "__main__":
    unittest.main()
