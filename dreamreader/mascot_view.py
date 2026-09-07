"""Single-window companion, with a lit 3D mesh rendered on Tk's canvas."""
from __future__ import annotations

import json
import math
import os
import sys
import time
import tkinter as tk

from . import PROJECT_ROOT
from .config import load_config
from .robot_surface import company_logo
from .companion_art import companion_frame
from PIL import ImageTk, Image

BG = "#f2f4ed"
KEY = "#ff00ff"


class CompanionView:
    def setup_view(self, root):
        self.expanded = False
        self.page = None
        self.pending = "0"
        self.birth = time.monotonic()
        self.reaction = 0
        self.state_var = tk.StringVar(value=self.status)
        self.info_var = tk.StringVar()
        root.title("RiegoBot · Mascota")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=KEY)
        if sys.platform == "win32":
            root.wm_attributes("-transparentcolor", KEY)
        root.geometry(f"420x340+{max(0, root.winfo_screenwidth()-460)}+{max(0, root.winfo_screenheight()-740)}")
        self.canvas = tk.Canvas(root, width=420, height=340, bg=KEY, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.move)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Button-3>", lambda e: self.show_panel())
        root.bind("<Escape>", lambda e: self.collapse())
        self.controls = tk.Frame(root, bg=BG, padx=20, pady=14)
        header = tk.Frame(self.controls, bg=BG)
        header.pack(fill="x")
        self.logo_image = ImageTk.PhotoImage(company_logo().resize((48,48), Image.Resampling.LANCZOS))
        tk.Label(header, image=self.logo_image, bg=BG, bd=0).pack(side="left", padx=(0,12))
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left")
        tk.Label(titles, text="RiegoBot", bg=BG, fg="#243e2d", font=("Segoe UI",16,"bold")).pack(anchor="w")
        tk.Label(titles, text="Asistente de riego · Camposol", bg=BG, fg="#66745f", font=("Segoe UI",9)).pack(anchor="w")
        tk.Label(self.controls, textvariable=self.state_var, bg=BG, fg="#243e2d", wraplength=375, justify="left", font=("Segoe UI", 10)).pack(anchor="w", pady=(8, 5))
        tk.Label(self.controls, textvariable=self.info_var, bg=BG, fg="#68755f", justify="left", font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(self.controls, bg=BG)
        row.pack(fill="x", pady=10)
        self.action_buttons = []
        self.run_button = self.button(row, "Iniciar automático", self.toggle_running, side="left", accent=True)
        self.sync_button = self.button(row, "Sincronizar ahora", self.once, side="left")
        self.action_buttons.extend((self.run_button, self.sync_button))
        nav = tk.Frame(self.controls, bg=BG)
        nav.pack(fill="x")
        for label, action in [("Ajustes", self.config), ("Actividad", self.logs), ("Minimizar", self.collapse), ("Salir", self.close)]:
            self.button(nav, label, action, side="left")
        self.content_host = tk.Frame(self.controls, bg=BG)
        self.content_host.pack(fill="both", expand=True)
        self.page_canvas = tk.Canvas(self.content_host, bg=BG, highlightthickness=0)
        self.page_scroll = tk.Scrollbar(self.content_host, orient="vertical", command=self.page_canvas.yview)
        self.page_canvas.configure(yscrollcommand=self.page_scroll.set)
        self.page_canvas.pack(side="left", fill="both", expand=True)
        self.content = tk.Frame(self.page_canvas, bg=BG)
        self.content_window = self.page_canvas.create_window((0,0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda e: self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all")))
        self.page_canvas.bind("<Configure>", lambda e: self.page_canvas.itemconfigure(self.content_window, width=e.width))
        self.page_canvas.bind("<MouseWheel>", lambda e: self.page_canvas.yview_scroll(-int(e.delta/120),"units"))
        self.frame_key = None
        self.animate()

    def toggle_running(self):
        if self.running:
            self.pause()
        else:
            self.start()

    def button(self, parent, label, action, side="top", accent=False):
        b = tk.Button(parent, text=label, command=action, font=("Segoe UI", 9), bg="#31563a" if accent else "#e5eade", fg="white" if accent else "#30452e", activebackground="#cbdabe", relief="flat", bd=0, padx=10, pady=7, cursor="hand2")
        base = b.cget("bg")
        b.configure(highlightthickness=1, highlightbackground=base, highlightcolor="#d2c28d", takefocus=True)
        b.bind("<Enter>", lambda e: b.configure(bg="#46724b" if accent else "#d8e2cd"))
        b.bind("<Leave>", lambda e: b.configure(bg=base))
        b.pack(side=side, padx=(0, 5), pady=2)
        return b

    def resize(self):
        target_height = 340 if not self.expanded else (790 if self.page else 600)
        height = min(target_height, max(480,self.root.winfo_screenheight()-90)) if self.expanded else 340
        self.root.geometry(f"420x{height}")
        self.root.update_idletasks()
        x = max(0, min(self.root.winfo_x(), self.root.winfo_screenwidth()-420))
        y = max(0, min(self.root.winfo_y(), self.root.winfo_screenheight()-height-45))
        self.root.geometry(f"+{x}+{y}")

    def show_panel(self):
        self.reaction = time.monotonic()
        if self.expanded:
            self.collapse()
        else:
            self.expanded = True
            self.controls.pack(fill="both", expand=True, padx=12)
            self.resize()

    def collapse(self):
        self.expanded = False
        self.controls.pack_forget()
        self.resize()

    def press(self, e):
        self.drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())

    def move(self, e):
        if self.drag:
            x, y, rx, ry = self.drag
            nx = max(0, min(self.root.winfo_screenwidth()-420, rx+e.x_root-x))
            ny = max(0, min(self.root.winfo_screenheight()-self.root.winfo_height(), ry+e.y_root-y))
            self.root.geometry(f"+{nx}+{ny}")

    def release(self, e):
        if self.drag and abs(e.x_root-self.drag[0])+abs(e.y_root-self.drag[1]) < 6:
            self.show_panel()
        self.drag = None

    def draw(self):
        c = self.canvas
        c.delete("all")
        now = time.monotonic()
        t = now - self.birth
        bounce = math.sin(t*1.7)*1.2
        mouse_x = max(-1,min(1,(self.root.winfo_pointerx()-self.root.winfo_rootx()-210)/210))
        lean = round(mouse_x*2)/2
        blink = (t % 5.6 > 5.43)
        frame_key = (lean, blink)
        if frame_key != self.frame_key:
            self.robot_image = ImageTk.PhotoImage(companion_frame(*frame_key))
            self.frame_key = frame_key
        c.create_image(0, bounce, anchor="nw", image=self.robot_image)
        self.run_button.configure(text="Pausar automático" if self.running else "Iniciar automático", state="disabled" if self.closing else "normal")
        self.sync_button.configure(state="disabled" if self.busy or self.closing else "normal")
        caption = "Sincronizando…" if self.busy else ("Automático activo" if self.running else "Toca para ver controles")
        c.create_rectangle(109, 309, 311, 337, fill="#2c4733", outline="")
        c.create_text(210, 323, text=caption, fill="#e5f3de", font=("Segoe UI", 10))

    def animate(self):
        self.draw()
        self.root.after(80, self.animate)

    def clear_content(self, page):
        for widget in self.content.winfo_children():
            widget.destroy()
        self.page = page
        if page:
            self.page_scroll.pack(side="right",fill="y",before=self.page_canvas)
            self.button(self.content, "‹ Volver al estado", lambda: self.clear_content(None))
        else:
            self.page_scroll.pack_forget()
        self.page_canvas.yview_moveto(0)
        self.resize()

    def config(self):
        self.clear_content("config")
        cfg = load_config(PROJECT_ROOT)
        values = {}
        for label, value in [("Carpeta Dream", cfg.get("discovery", {}).get("rootPath", "")), ("URL Supabase", cfg.get("supabase", {}).get("url", "")), ("ID recolector", cfg.get("supabase", {}).get("collectorId", "")), ("Intervalo (s)", str(cfg.get("supabase", {}).get("intervalSeconds", 60))), ("Token (sesión)", os.environ.get("RIEGOBOT_COLLECTOR_TOKEN", ""))]:
            row = tk.Frame(self.content, bg=BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, width=16, anchor="w", bg=BG, fg="#53654d", font=("Segoe UI", 9)).pack(side="left")
            entry = tk.Entry(row, relief="flat", bg="white", fg="#243e2d", insertbackground="#243e2d", show="•" if label.startswith("Token") else "")
            entry.insert(0, value)
            entry.pack(side="left", fill="x", expand=True)
            values[label] = entry
        def save():
            try:
                interval = int(values["Intervalo (s)"].get())
                if interval < 30:
                    raise ValueError("El intervalo mínimo es 30 segundos.")
                url = values["URL Supabase"].get().strip().rstrip("/")
                if not (url.startswith("https://") or url.startswith("http://127.0.0.1:")):
                    raise ValueError("Indica una URL HTTPS de Supabase.")
                path = PROJECT_ROOT / "config/config.local.json"
                local = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                local.setdefault("discovery", {})["rootPath"] = values["Carpeta Dream"].get().strip()
                local.setdefault("supabase", {}).update(url=url, collectorId=values["ID recolector"].get().strip(), intervalSeconds=interval)
                local["readOnly"] = True
                temporary = path.with_suffix(".json.tmp")
                temporary.write_text(json.dumps(local, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                temporary.replace(path)
                os.environ["RIEGOBOT_COLLECTOR_TOKEN"] = values["Token (sesión)"].get().strip()
                self.set_status("Ajustes guardados. Token solo para esta sesión.", "#b6df93")
            except (ValueError, OSError) as exc:
                self.set_status(str(exc), "#d49a38")
        self.button(self.content, "Guardar ajustes", save)

    def logs(self):
        self.clear_content("logs")
        text = tk.Text(self.content, height=8, bg="white", fg="#374831", font=("Consolas", 8), wrap="word", relief="flat")
        text.pack(fill="both", expand=True, pady=7)
        path = PROJECT_ROOT / "runtime/mascot.log"
        if path.exists():
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size-10000))
                content = stream.read().decode("utf-8", errors="replace")
        else:
            content = "Todavía no hay ciclos registrados."
        token = os.environ.get("RIEGOBOT_COLLECTOR_TOKEN")
        if token:
            content = content.replace(token, "[token oculto]")
        text.insert("1.0", content)
        text.see("end")
        text.configure(state="disabled")
