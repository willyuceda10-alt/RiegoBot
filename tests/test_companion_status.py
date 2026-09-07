"""Connection colour follows acknowledged results, not decorative animation."""
import os
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dreamreader import mascot


class CompanionStatusTests(unittest.TestCase):
    def setUp(self):
        # No display, Tk main loop, real collector, or network is needed.
        self.app = mascot.Mascot.__new__(mascot.Mascot)
        self.app.running = False
        self.app.busy = False
        self.app.closing = False
        self.app.next_run = 0
        self.app.last_confirmed_at = None
        self.app.connection_failed = False
        self.app.paused_by_user = True
        self.app.connection_interval = 60
        self.app.last_success = "Nunca"
        self.app.status_kind = "config"
        self.app.state_var = Mock()
        self.app.info_var = Mock()
        self.app.draw = Mock()
        self.app.root = Mock()
        self.app.events = queue.Queue()
        self.app.pending_checked_at = 100
        self.app.pending = "0"
        self.cfg = {"readOnly": True, "supabase": {
            "url": "https://example.supabase.co", "intervalSeconds": 60}}

    def finish_cycle(self, success, now=100):
        self.app.events.put(success)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(mascot, "PROJECT_ROOT", Path(directory)), \
                patch.object(mascot, "load_config", return_value=self.cfg), \
                patch.object(mascot.time, "monotonic", return_value=now):
            self.app.tick()

    def start_manual_cycle(self):
        with patch.object(mascot, "load_config", return_value=self.cfg), \
                patch.dict(os.environ, {"RIEGOBOT_COLLECTOR_TOKEN": "test-only"}), \
                patch.object(mascot.threading, "Thread") as thread:
            self.app.once()
            thread.return_value.start.assert_called_once()

    def test_initial_and_first_read_are_waiting(self):
        self.assertEqual(self.app.visual_status(100), "waiting")
        self.start_manual_cycle()
        self.assertTrue(self.app.busy)
        self.assertFalse(self.app.paused_by_user)
        self.assertEqual(self.app.visual_status(100), "waiting")
        self.assertEqual(self.app.connection_interval, 60)

    def test_manual_success_is_online_until_contact_expires(self):
        self.start_manual_cycle()
        self.finish_cycle(True)
        self.assertFalse(self.app.running)
        self.assertFalse(self.app.busy)
        self.assertEqual(self.app.last_confirmed_at, 100)
        self.assertEqual(self.app.visual_status(219.99), "online")
        self.assertEqual(self.app.visual_status(220), "waiting")

    def test_freshness_window_has_minimum_and_maximum(self):
        self.app.status_kind = "ready"
        self.app.paused_by_user = False
        self.app.last_confirmed_at = 100
        for interval, lifetime in ((30, 90), (60, 120), (86400, 300)):
            with self.subTest(interval=interval):
                self.app.connection_interval = interval
                self.assertEqual(self.app.visual_status(100+lifetime-0.01), "online")
                self.assertEqual(self.app.visual_status(100+lifetime), "waiting")
        self.assertEqual(self.app.visual_status(99), "waiting")

    def test_busy_cannot_extend_expired_contact(self):
        self.start_manual_cycle()
        self.finish_cycle(True)
        self.app.busy = True
        self.assertEqual(self.app.visual_status(110), "online")
        self.assertEqual(self.app.visual_status(400), "waiting")

    def test_failure_survives_start_until_successful_retry(self):
        self.start_manual_cycle()
        self.finish_cycle(False)
        self.assertEqual(self.app.visual_status(101), "error")
        self.app.start()
        self.assertEqual(self.app.visual_status(101), "error")
        self.start_manual_cycle()
        self.assertEqual(self.app.visual_status(101), "error")
        self.finish_cycle(True, 110)
        self.assertEqual(self.app.visual_status(111), "online")

    def test_pausing_in_flight_stays_waiting_after_success(self):
        self.start_manual_cycle()
        self.app.pause()
        self.finish_cycle(True)
        self.assertTrue(self.app.paused_by_user)
        self.assertEqual(self.app.visual_status(101), "waiting")
        self.start_manual_cycle()
        self.finish_cycle(True, 110)
        self.assertEqual(self.app.visual_status(111), "online")

    def test_saving_connection_requires_new_acknowledgement(self):
        self.start_manual_cycle()
        self.finish_cycle(True)
        self.app.invalidate_connection()
        self.app.set_status("Ajustes guardados", "#63ab65", "ready")
        self.assertEqual(self.app.visual_status(101), "waiting")
        self.finish_cycle(False, 110)
        self.app.invalidate_connection()
        self.app.set_status("Ajustes guardados", "#63ab65", "ready")
        self.assertFalse(self.app.connection_failed)
        self.assertEqual(self.app.visual_status(111), "waiting")

    def test_invalid_configuration_cannot_keep_old_green_contact(self):
        self.start_manual_cycle()
        self.finish_cycle(True)
        with patch.object(mascot, "load_config", return_value=self.cfg), \
                patch.dict(os.environ, {"RIEGOBOT_COLLECTOR_TOKEN": ""}):
            self.app.once()
        self.assertEqual(self.app.status_kind, "config")
        self.assertIsNone(self.app.last_confirmed_at)
        self.assertEqual(self.app.visual_status(101), "error")

    def test_closing_is_waiting_even_after_failure(self):
        self.start_manual_cycle()
        self.finish_cycle(False)
        self.app.busy = True
        self.app.close()
        self.assertEqual(self.app.visual_status(101), "waiting")


if __name__ == "__main__":
    unittest.main()
