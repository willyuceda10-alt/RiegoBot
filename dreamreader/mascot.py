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


class Mascot:
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
        root.title("RiegoBot · Mascota")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg="#ff00ff")
        if sys.platform == "win32":
            root.wm_attributes("-transparentcolor", "#ff00ff")
        root.geometry(f"190x210+{root.winfo_screenwidth()-230}+{root.winfo_screenheight()-310}")
        self.canvas = tk.Canvas(root, width=190, height=210, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.move)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Button-3>", lambda e: self.show_panel())
        self.panel = tk.Toplevel(root)
        self.panel.title("RiegoBot · Recolector Dream")
        self.panel.geometry("440x490")
        self.panel.configure(bg="#f4f7f2")
        self.panel.protocol("WM_DELETE_WINDOW", self.panel.withdraw)
        self.label("TU ASISTENTE DE RIEGO", 10, "#60766b").pack(anchor="w", padx=28, pady=(26, 5))
        self.label("Dream, acompañado.", 23, "#173f30").pack(anchor="w", padx=28)
        self.state_var = tk.StringVar(value=self.status)
        tk.Label(self.panel, textvariable=self.state_var, font=("Segoe UI", 13, "bold"), bg="#f4f7f2", fg="#173f30", wraplength=380).pack(anchor="w", padx=28, pady=(22, 10))
        self.info_var = tk.StringVar()
        tk.Label(self.panel, textvariable=self.info_var, justify="left", wraplength=380, bg="#f4f7f2", fg="#53665a", font=("Segoe UI", 10)).pack(anchor="w", padx=28)
        controls = tk.Frame(self.panel, bg="#f4f7f2")
        controls.pack(fill="x", padx=28, pady=20)
        for text, action in [("Iniciar", self.start), ("Pausar", self.pause), ("Sincronizar", self.once)]:
            tk.Button(controls, text=text, command=action, bg="#1e6248", fg="white", relief="flat", padx=12, pady=9).pack(side="left", padx=(0, 8))
        for text, action in [("Abrir configuración local", self.config), ("Ver registro de actividad", self.logs), ("Ocultar controles", self.panel.withdraw), ("Salir de la mascota", self.close)]:
            tk.Button(self.panel, text=text, command=action, bg="#f4f7f2", fg="#1e6248", relief="flat", anchor="w").pack(fill="x", padx=25, pady=2)
        self.label("Solo lectura · No acciona equipos", 9, "#60766b").pack(anchor="w", padx=28, pady=14)
        self.draw()
        self.tick()

    def label(self, text, size, color):
        return tk.Label(self.panel, text=text, font=("Segoe UI", size), bg="#f4f7f2", fg=color)

    def draw(self):
        c = self.canvas
        c.delete("all")
        c.create_oval(42, 157, 150, 176, fill="#b7cabe", outline="")
        c.create_polygon(94, 22, 58, 72, 40, 113, 46, 146, 69, 164, 114, 164, 143, 145, 151, 114, 135, 76, fill="#267754", smooth=True, outline="#174a35", width=3)
        c.create_oval(58, 79, 132, 139, fill="#e5f3dd", outline="")
        c.create_oval(75, 96, 82, 106, fill="#173f30", outline="")
        c.create_oval(109, 96, 116, 106, fill="#173f30", outline="")
        c.create_arc(82, 103, 110, 123, start=190, extent=160, style="arc", outline="#173f30", width=3)
        c.create_oval(97, 23, 125, 41, fill="#a6ce73", outline="")
        c.create_oval(139, 142, 157, 160, fill=self.color, outline="#f4f7f2", width=3)
        c.create_text(95, 191, text="RiegoBot · clic para abrir", fill="#173f30", font=("Segoe UI", 9, "bold"))

    def press(self, e):
        self.drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())

    def move(self, e):
        if self.drag:
            x, y, rx, ry = self.drag
            self.root.geometry(f"+{max(0, min(self.root.winfo_screenwidth()-190, rx+e.x_root-x))}+{max(0, min(self.root.winfo_screenheight()-210, ry+e.y_root-y))}")

    def release(self, e):
        if self.drag and abs(e.x_root-self.drag[0])+abs(e.y_root-self.drag[1]) < 6:
            self.show_panel()
        self.drag = None

    def show_panel(self):
        self.panel.deiconify()
        self.panel.lift()

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
                raise ValueError("Falta RIEGOBOT_COLLECTOR_TOKEN. Configúralo en Windows y vuelve a abrir la mascota.")
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
        self.info_var.set(f"Último ciclo correcto: {self.last_success}\nLotes pendientes: {pending}\nAutomático: {'activo' if self.running else 'pausado'}\nEl estado corresponde al recolector, no a las válvulas.")
        self.root.after(1000, self.tick)

    def config(self):
        path = PROJECT_ROOT / "config/config.local.json"
        if not path.exists():
            path.write_text('{}\n', encoding="utf-8")
        os.startfile(str(path))

    def logs(self):
        path = PROJECT_ROOT / "runtime/mascot.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        os.startfile(str(path))

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
