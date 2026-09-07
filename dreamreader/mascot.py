"""Windows desktop companion for the read-only Dream collector (stdlib only)."""
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
        self.color = "#82978e"
        self.drag = None
        self.setup_view(root)
        self.tick()

    def start(self):
        if not self.closing:
            self.running = True
            self.next_run = 0

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
        except Exception as exc:
            self.running = False
            self.set_status(str(exc), "#c36a47")
            return
        self.busy = True
        self.set_status("Leyendo Dream y enviando datos…", "#e7b64e")
        threading.Thread(target=self.collect, daemon=True).start()

    def collect(self):
        log = PROJECT_ROOT / "runtime/mascot.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            executable = str(Path(sys.executable).with_name("python.exe")) if sys.executable.lower().endswith("pythonw.exe") else sys.executable
            with log.open("a", encoding="utf-8") as output:
                output.write(f"\n--- {datetime.now().isoformat()} ---\n")
                output.flush()
                result = subprocess.run([executable, "-m", "dreamreader.collector", "--once"], cwd=PROJECT_ROOT, stdout=output, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.events.put(result.returncode == 0)
        except Exception:
            self.events.put(False)

    def set_status(self, text, color):
        self.status, self.color = text, color
        self.state_var.set(text)
        self.draw()

    def tick(self):
        try:
            success = self.events.get_nowait()
            self.busy = False
            if success:
                self.last_success = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.set_status("Sincronización completada" if success else "No se completó el ciclo. Revisa el registro.", "#63ab65" if success else "#c36a47")
            try:
                interval = max(30, int(load_config(PROJECT_ROOT).get("supabase", {}).get("intervalSeconds", 60)))
            except Exception:
                interval = 60
            self.next_run = time.monotonic() + interval
        except queue.Empty:
            pass
        if self.closing and not self.busy:
            self.root.destroy()
            return
        if self.running and not self.busy and time.monotonic() >= self.next_run:
            self.once()
        pending = "0"
        path = PROJECT_ROOT / "runtime/outbox.sqlite"
        if path.exists():
            try:
                with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True, timeout=0.1) as db:
                    pending = str(db.execute("SELECT count(*) FROM outbox").fetchone()[0])
            except sqlite3.Error:
                pending = "Consultando…"
        self.info_var.set(f"Último envío: {self.last_success}\nLotes pendientes: {pending} · {'Automático' if self.running else 'Pausado'}")
        self.root.after(1000, self.tick)

    def close(self):
        self.running = False
        self.closing = True
        if self.busy:
            self.set_status("Cerrando cuando termine el ciclo…", "#d49a38")
        else:
            self.root.destroy()


def main():
    with socket.socket() as lock:
        try:
            lock.bind(("127.0.0.1", 55329))
        except OSError:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("RiegoBot", "La mascota ya está abierta o su puerto local está ocupado.")
            root.destroy()
            return
        root = tk.Tk()
        Mascot(root)
        root.mainloop()


if __name__ == "__main__":
    main()
