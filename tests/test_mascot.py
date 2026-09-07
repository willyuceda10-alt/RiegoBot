"""Regression checks for actual desktop interaction and failure recovery."""
import os
import queue
import subprocess
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dreamreader import mascot, mascot_view


class CollectorUiFailureTests(unittest.TestCase):
    def test_watchdog_failure_still_kills_child_and_completes(self):
        for failure in (FileNotFoundError(), subprocess.TimeoutExpired("taskkill", 15)):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as directory:
                app = mascot.Mascot.__new__(mascot.Mascot)
                app.events = queue.Queue()
                app.running = True
                process = Mock(pid=999999)
                process.poll.return_value = None
                process.wait.side_effect = [subprocess.TimeoutExpired("collector", 301), 0]
                with patch.object(mascot, "PROJECT_ROOT", Path(directory)), patch.object(mascot, "load_config", return_value={}), patch.object(mascot.sys, "platform", "win32"), patch.object(mascot.subprocess, "Popen", return_value=process), patch.object(mascot.subprocess, "run", side_effect=failure):
                    app.collect()
                process.kill.assert_called_once()
                self.assertEqual(process.wait.call_args.kwargs, {"timeout": 5})
                self.assertIs(app.events.get_nowait(), False)
                self.assertFalse(app.running)

    def test_log_directory_failure_always_completes_event(self):
        app = mascot.Mascot.__new__(mascot.Mascot)
        app.events = queue.Queue()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "runtime").write_text("not a directory", encoding="utf-8")
            with patch.object(mascot, "PROJECT_ROOT", base):
                app.collect()
        self.assertIs(app.events.get_nowait(), False)
        self.assertTrue(app.events.empty())

    def test_pending_connection_closed_and_poll_throttled(self):
        app = mascot.Mascot.__new__(mascot.Mascot)
        app.events = queue.Queue()
        app.closing = app.running = app.busy = False
        app.last_success = "Nunca"
        app.pending_checked_at = 0
        app.pending = "0"
        app.info_var = Mock()
        app.root = Mock()
        db = Mock()
        db.execute.return_value.fetchone.return_value = (17,)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "runtime").mkdir()
            (base / "runtime/outbox.sqlite").touch()
            with patch.object(mascot, "PROJECT_ROOT", base), patch.object(mascot.sqlite3, "connect", return_value=db) as connect, patch.object(mascot.time, "monotonic", return_value=100):
                app.tick()
                app.tick()
                connect.assert_called_once()
        db.close.assert_called_once()
        self.assertEqual(app.pending, "17")


class DesktopInteractionTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        self.root.withdraw()
        self.root.attributes("-alpha", 0)
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.cfg = {"readOnly": True, "discovery": {"rootPath": str(self.base)}, "supabase": {
            "url": "https://example.supabase.co", "collectorId": "00000000-0000-0000-0000-000000000001", "intervalSeconds": 60}}
        self.patches = [patch.object(mascot, "PROJECT_ROOT", self.base), patch.object(mascot_view, "PROJECT_ROOT", self.base),
                        patch.object(mascot, "load_config", return_value=self.cfg), patch.object(mascot_view, "load_config", return_value=self.cfg)]
        for patcher in self.patches:
            patcher.start()
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.app = mascot.Mascot(self.root)
        self.root.update()

    def tearDown(self):
        if hasattr(self, "app"):
            self.app.destroy()
            for patcher in reversed(self.patches):
                patcher.stop()
            self.directory.cleanup()
            self.assertEqual(self.errors, [])

    def test_keyboard_open_escape_and_error_visibility(self):
        self.root.deiconify()
        self.app.caption_button.focus_force()
        self.root.update()
        self.app.caption_button.event_generate("<Return>")
        self.root.update()
        self.assertTrue(self.app.expanded)
        self.assertEqual(self.root.focus_get(), self.app.run_button)
        self.root.event_generate("<Escape>")
        self.root.update()
        self.assertFalse(self.app.expanded)
        self.assertEqual(self.root.focus_get(), self.app.caption_button)
        self.app.set_status("Fallo de prueba", "#c36a47", "error")
        self.assertIn("fallo", self.app.caption_button.cget("text"))
        with patch.dict(os.environ):
            os.environ.pop("RIEGOBOT_COLLECTOR_TOKEN", None)
            self.app.once()
        self.assertFalse(self.app.busy)
        self.assertEqual(self.app.caption_button.cget("text"), "Revisar fallo")

    def test_reduced_motion_no_canvas_or_image_growth(self):
        self.app.reduced_motion.set(True)
        self.app.draw()
        items = self.app.canvas.find_all()
        images = self.root.tk.call("image", "names")
        with patch.object(mascot_view.time, "monotonic", side_effect=range(100, 500)):
            for _ in range(300):
                self.app.draw()
        self.assertEqual(items, self.app.canvas.find_all())
        self.assertEqual(images, self.root.tk.call("image", "names"))
        self.app.busy = True
        self.app.draw()
        self.assertEqual(self.app.sync_button.cget("state"), "disabled")
        self.assertIn("Leyendo", self.app.caption_button.cget("text"))

    def test_active_motion_reuses_images_and_thought_is_the_only_status_action(self):
        self.root.deiconify()
        self.root.update()
        self.assertLess(self.app.caption_button.winfo_y(), 40)
        self.assertEqual(self.app.canvas.winfo_height(), 210)
        images = self.root.tk.call("image", "names")
        items = self.app.canvas.find_all()
        for i in range(90):
            with patch.object(mascot_view.time, "monotonic", return_value=self.app.birth+i/30):
                self.app.draw()
        self.assertEqual(images, self.root.tk.call("image", "names"))
        self.assertEqual(items, self.app.canvas.find_all())
        self.app.status_kind = "ready"
        self.app.paused_by_user = False
        self.app.last_confirmed_at = self.app.birth
        with patch.object(mascot_view.time, "monotonic", return_value=self.app.birth+1):
            self.app.draw()
            self.assertEqual(self.app.caption_button.cget("text"), "En línea")
            self.assertEqual(self.app.caption_button.cget("bg"), mascot_view.PALETTES["online"]["fill"])
            self.app.connection_failed = True
            self.app.draw()
            self.assertEqual(self.app.caption_button.cget("text"), "Revisar fallo")
            self.assertEqual(self.app.caption_button.cget("bg"), mascot_view.PALETTES["error"]["fill"])

    def test_large_text_and_scroll_follow_keyboard_focus(self):
        self.root.tk.call("tk", "scaling", 2.667)
        self.app.open_controls()
        self.app.config()
        self.app.large_text.set(True)
        self.app.save_preferences()
        self.root.update()
        self.assertLessEqual(self.root.winfo_width(), self.root.winfo_screenwidth())
        self.assertLessEqual(self.root.winfo_height(), self.root.winfo_screenheight()-60)
        field = self.app.entries["Token (sesión)"]
        field.focus_force()
        self.root.update()
        top = self.app.panel_canvas.winfo_rooty()
        self.assertGreaterEqual(field.winfo_rooty(), top-1)
        self.assertLessEqual(field.winfo_rooty()+field.winfo_height(), top+self.app.panel_canvas.winfo_height()+1)
        self.assertLessEqual(field.winfo_width(), self.app.panel_canvas.winfo_width())
        self.assertGreater(self.app.panel_canvas.yview()[0], 0)
        self.app.running = True
        self.app.status_kind = "ready"
        self.app.draw()
        self.root.update_idletasks()
        self.assertLessEqual(self.app.caption_button.winfo_reqheight(), 28)
        self.assertLessEqual(self.app.caption_button.winfo_reqwidth(), 104)
        self.app.connection_failed = True
        self.app.draw()
        self.root.update_idletasks()
        self.assertLessEqual(self.app.caption_button.winfo_reqheight(), 28)
        self.assertLessEqual(self.app.caption_button.winfo_reqwidth(), 104)
        self.app.reduced_motion.set(True)
        self.app.save_preferences()
        self.assertIn('"reducedMotion": true', self.app.preferences_path.read_text())

    def test_config_rejects_credential_url_and_never_persists_token(self):
        self.app.open_controls()
        self.app.config()
        url = self.app.entries["URL Supabase"]
        url.delete(0, "end")
        url.insert(0, "http://127.0.0.1:80@attacker.invalid")
        self.app.save_config()
        self.assertFalse((self.base / "config/config.local.json").exists())
        self.assertIn("HTTPS", self.app.config_error.get())
        url.delete(0, "end")
        url.insert(0, self.cfg["supabase"]["url"])
        token = self.app.entries["Token (sesión)"]
        token.delete(0, "end")
        token.insert(0, "unit-test-token-not-a-secret")
        with patch.dict(os.environ):
            self.app.save_config()
            saved = (self.base / "config/config.local.json").read_text()
            self.assertNotIn("unit-test-token", saved)
            self.assertEqual(os.environ["RIEGOBOT_COLLECTOR_TOKEN"], "unit-test-token-not-a-secret")


if __name__ == "__main__":
    unittest.main()
