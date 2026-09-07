"""Windows desktop companion for the read-only Dream collector."""
from __future__ import annotations

import os
import queue
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
from contextlib import closing
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from . import PROJECT_ROOT
from .config import load_config
from .mascot_view import CompanionView


class Mascot(CompanionView):
    def __init__(self, root: tk.Tk):
        self.root = root
        self.events = queue.Queue()
        self.running = False
        self.busy = False
        self.closing = False
        self.next_run = 0.0
        self.last_success = "Todavía no se ha sincronizado"
        self.status = "Listo para configurar"
        self.status_kind = "config"
        self.color = "#82978e"
        self.drag = None
        self.pending = "0"
        self.pending_checked_at = 0.0
        self.setup_view(root)
        self.tick()

    def start(self):
        if not self.closing:
            self.running = True
            self.next_run = 0
            self.set_status("Automático iniciado. Preparando lectura…", "#63ab65")

    def pause(self):
        self.running = False
        self.set_status("Pausando al terminar el ciclo…" if self.busy else "En pausa", "#d49a38")

    def once(self):
        if self.busy or self.closing:
            return
        try:
            cfg = load_config(PROJECT_ROOT)
            if not cfg.get("readOnly"):
                raise ValueError("Activa readOnly en la configuración.")
            if not os.environ.get("RIEGOBOT_COLLECTOR_TOKEN"):
                raise ValueError("Falta el token del recolector. Agrégalo en Ajustes.")
            from .collector import ingest_endpoint
            ingest_endpoint(cfg.get("supabase", {}).get("url", ""))
        except (ValueError, OSError, TypeError, AttributeError):
            self.running = False
            self.set_status("Revisa URL, token y modo de solo lectura en Ajustes.", "#c36a47", "config")
            return
        self.busy = True
        self.set_status("Leyendo Dream y enviando datos…", "#e7b64e")
        threading.Thread(target=self.collect, daemon=True).start()

    def collect(self):
        log = PROJECT_ROOT / "runtime/mascot.log"
        success = False
        process = None
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            if log.exists() and log.stat().st_size >= 2*1024*1024:
                log.replace(log.with_suffix(".log.1"))
            executable = str(Path(sys.executable).with_name("python.exe")) if sys.executable.lower().endswith("pythonw.exe") else sys.executable
            settings = load_config(PROJECT_ROOT).get("supabase", {})
            timeout = min(3600, max(1, int(settings.get("extractionTimeoutSeconds", 900))))+300
            with log.open("a", encoding="utf-8") as output:
                output.write(f"\n--- {datetime.now().isoformat()} ---\n")
                output.flush()
                # Popen.__exit__ waits without a timeout. Explicit cleanup below
                # must run even if taskkill fails or the log becomes unwritable.
                try:
                    process = subprocess.Popen([executable, "-m", "dreamreader.collector", "--once"], cwd=PROJECT_ROOT, stdout=output, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    try:
                        success = process.wait(timeout=timeout) == 0
                    except subprocess.TimeoutExpired:
                        output.write("\nSe agotó el tiempo máximo del ciclo; los lotes pendientes se conservan.\n")
                finally:
                    if process is not None and process.poll() is None:
                        success = False
                        tree_stopped = sys.platform != "win32"
                        # Target only the owned PID and its descendants. The
                        # absolute executable path avoids PATH substitution.
                        if sys.platform == "win32":
                            taskkill = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"
                            try:
                                result = subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                                tree_stopped = result.returncode == 0
                            except (OSError, subprocess.TimeoutExpired):
                                tree_stopped = False
                        # Always attempt direct termination even if taskkill
                        # failed. Never use an unbounded wait in this worker.
                        try:
                            if process.poll() is None:
                                process.kill()
                            process.wait(timeout=5)
                        except (OSError, subprocess.TimeoutExpired):
                            tree_stopped = False
                        if not tree_stopped:
                            self.running = False
                            output.write("\nNo se pudo confirmar el cierre de todo el árbol del recolector. Automático detenido; revisa los procesos de DreamReader antes de reanudar.\n")
        except Exception:
            success = False
        finally:
            # Include mkdir/open/config failures; otherwise busy would remain true forever.
            self.events.put(success)

    def set_status(self, text, color, kind="ready"):
        self.status, self.color = text, color
        self.status_kind = kind
        self.state_var.set(text)
        self.draw()

    def tick(self):
        try:
            success = self.events.get_nowait()
            self.busy = False
            if success:
                self.last_success = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.set_status("Sincronización completada" if success else "No se completó el ciclo. Revisa el registro.", "#63ab65" if success else "#c36a47", "ready" if success else "error")
            try:
                interval = max(30, int(load_config(PROJECT_ROOT).get("supabase", {}).get("intervalSeconds", 60)))
            except Exception:
                interval = 60
            self.next_run = time.monotonic() + interval
        except queue.Empty:
            pass
        if self.closing and not self.busy:
            self.destroy()
            return
        if self.running and not self.busy and time.monotonic() >= self.next_run:
            self.once()
        path = PROJECT_ROOT / "runtime/outbox.sqlite"
        if time.monotonic()-self.pending_checked_at >= 5:
            self.pending_checked_at = time.monotonic()
            self.pending = "0"
            try:
                if path.exists():
                    with closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True, timeout=0.025)) as db:
                        self.pending = str(db.execute("SELECT count(*) FROM outbox").fetchone()[0])
            except sqlite3.Error:
                self.pending = "Consultando…"
        info = f"Último envío: {self.last_success}\nLotes pendientes: {self.pending} · {'Automático' if self.running else 'Pausado'}"
        if self.info_var.get() != info:
            self.info_var.set(info)
        self.tick_timer = self.root.after(1000, self.tick)

    def close(self):
        self.running = False
        self.closing = True
        if self.busy:
            self.set_status("Cerrando cuando termine el ciclo…", "#d49a38")
        else:
            self.destroy()

    def destroy(self):
        for timer in (getattr(self, "animation_timer", None), getattr(self, "tick_timer", None)):
            if timer:
                self.root.after_cancel(timer)
        self.root.destroy()


def main():
    with socket.socket() as lock:
        try:
            lock.bind(("127.0.0.1", 55329))
        except OSError:
            try:
                with socket.create_connection(("127.0.0.1", 55329), timeout=0.3) as existing:
                    existing.sendall(b"show\n")
                return
            except OSError:
                pass
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("RiegoBot", "La mascota ya está abierta o su puerto local está ocupado.")
            root.destroy()
            return
        root = tk.Tk()
        mascot = Mascot(root)
        lock.listen(2)
        lock.setblocking(False)
        def recover_window():
            try:
                connection, _ = lock.accept()
                with connection:
                    connection.settimeout(0.02)
                    if connection.recv(16) == b"show\n":
                        mascot.open_controls()
            except OSError:
                pass
            root.after(500, recover_window)
        recover_window()
        if "--controls" in sys.argv:
            mascot.open_controls()
        root.mainloop()


if __name__ == "__main__":
    main()
