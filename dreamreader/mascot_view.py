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

BG = "#142d29"
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
        root.geometry(f"420x280+{max(0, root.winfo_screenwidth()-460)}+{max(0, root.winfo_screenheight()-740)}")
        self.canvas = tk.Canvas(root, width=420, height=280, bg=KEY, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.move)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Button-3>", lambda e: self.show_panel())
        root.bind("<Escape>", lambda e: self.collapse())
        self.controls = tk.Frame(root, bg=BG, padx=20, pady=14)
        tk.Label(self.controls, text="R I E G O B O T", bg=BG, fg="#c7edb6", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(self.controls, textvariable=self.state_var, bg=BG, fg="white", wraplength=375, justify="left", font=("Segoe UI", 10)).pack(anchor="w", pady=(8, 5))
        tk.Label(self.controls, textvariable=self.info_var, bg=BG, fg="#a6bdb3", justify="left", font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(self.controls, bg=BG)
        row.pack(fill="x", pady=10)
        self.action_buttons = []
        for label, action in [("▶ Iniciar", self.start), ("Ⅱ Pausar", self.pause), ("↻ Sincronizar", self.once)]:
            self.action_buttons.append(self.button(row, label, action, side="left", accent=True))
        nav = tk.Frame(self.controls, bg=BG)
        nav.pack(fill="x")
        for label, action in [("Ajustes", self.config), ("Actividad", self.logs), ("Ocultar", self.collapse), ("Salir", self.close)]:
            self.button(nav, label, action, side="left")
        self.content = tk.Frame(self.controls, bg=BG)
        self.content.pack(fill="both", expand=True)
        self.mesh = []
        # A closed surface of revolution: round belly, tapered water-drop crown.
        latitudes, longitudes = 28, 44
        def point(i, j):
            theta = math.pi * i / latitudes
            phi = math.tau * j / longitudes
            radius = math.sin(theta) * (0.80 - 0.24 * math.cos(theta))
            return (radius * math.cos(phi), 1.10 * math.cos(theta), radius * math.sin(phi))
        for i in range(latitudes):
            for j in range(longitudes):
                self.mesh.append([point(i, j), point(i+1, j), point(i+1, j+1), point(i, j+1)])
        self.animate()

    def button(self, parent, label, action, side="top", accent=False):
        b = tk.Button(parent, text=label, command=action, font=("Segoe UI", 9), bg="#b6df93" if accent else BG, fg="#142d29" if accent else "#c6dacf", activebackground="#d3edbd", relief="flat", bd=0, padx=10, pady=7, cursor="hand2")
        b.pack(side=side, padx=(0, 5), pady=2)
        return b

    def resize(self):
        height = 280 if not self.expanded else (690 if self.page else 505)
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
        bounce = math.sin(t*2.0)*3 + (math.sin((now-self.reaction)*12)*6 if now-self.reaction < 0.7 else 0)
        yaw = math.sin(t*0.65)*0.14
        mouse_x = max(-1, min(1, (self.root.winfo_pointerx()-self.root.winfo_rootx()-210)/210))
        yaw += mouse_x*0.10
        scale = 76*(1+0.015*math.sin(t*2))
        def rotate(p):
            x, y, z = p
            return (x*math.cos(yaw)+z*math.sin(yaw), y, -x*math.sin(yaw)+z*math.cos(yaw))
        def project(p):
            x, y, z = p
            perspective = 5/(5-z)
            return (210+x*scale*perspective, 128-y*scale*perspective+bounce)
        c.create_oval(155, 214, 265, 228, fill="#20372e", outline="")
        faces = []
        for face in self.mesh:
            points = [rotate(p) for p in face]
            center = [sum(p[k] for p in points)/4 for k in range(3)]
            a = [points[1][k]-points[0][k] for k in range(3)]
            b = [points[3][k]-points[0][k] for k in range(3)]
            normal = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
            if sum(normal[k]*center[k] for k in range(3)) < 0:
                normal = [-v for v in normal]
            length = math.sqrt(sum(v*v for v in normal)) or 1
            n = [v/length for v in normal]
            if n[2] < -0.12:
                continue
            diffuse = max(0, -n[0]*0.45+n[1]*0.55+n[2]*0.70)
            gloss = max(0, -n[0]*0.25+n[1]*0.32+n[2]*0.914)**40
            rgb = [min(255, int(base*(0.36+0.62*diffuse)+gloss*150)) for base in (100, 202, 139)]
            color = '#%02x%02x%02x' % tuple(rgb)
            coords = [v for p in points for v in project(p)]
            faces.append((center[2], coords, color))
        for _, coords, color in sorted(faces):
            c.create_polygon(coords, fill=color, outline=color)
        # Face rides the projected front surface as the character turns.
        blink = t % 4.8 > 4.62
        for x in (-0.27, 0.27):
            px, py = project(rotate((x, 0.02, 0.79)))
            if blink:
                c.create_line(px-7, py, px+7, py, fill="#123a2d", width=4, capstyle="round")
            else:
                c.create_oval(px-8, py-11, px+8, py+11, fill="#123a2d", outline="")
                c.create_oval(px-3, py-7, px+2, py-2, fill="#f0ffed", outline="")
        mx, my = project(rotate((0, -0.22, 0.87)))
        c.create_arc(mx-13, my-8, mx+13, my+8, start=185, extent=170, style="arc", outline="#123a2d", width=3)
        c.create_oval(242, 53+bounce, 277, 67+bounce, fill="#c0e693", outline="#8dbb66", width=2)
        c.create_line(234, 66+bounce, 266, 59+bounce, fill="#5c9655", width=2)
        c.create_oval(273, 185, 289, 201, fill=self.color, outline="#e4f6dd", width=2)
        if self.busy:
            c.create_arc(146, 66, 275, 208, start=(t*110)%360, extent=65, style="arc", outline="#d5ed98", width=3)
        caption = "Sincronizando…" if self.busy else ("Automático activo" if self.running else "Toca para ver controles")
        c.create_rectangle(109, 239, 311, 267, fill=BG, outline="")
        c.create_text(210, 253, text=caption, fill="#e5f3de", font=("Segoe UI", 10))

    def animate(self):
        self.draw()
        self.root.after(50, self.animate)

    def clear_content(self, page):
        for widget in self.content.winfo_children():
            widget.destroy()
        self.page = page
        self.resize()

    def config(self):
        self.clear_content("config")
        cfg = load_config(PROJECT_ROOT)
        values = {}
        for label, value in [("Carpeta Dream", cfg.get("discovery", {}).get("rootPath", "")), ("URL Supabase", cfg.get("supabase", {}).get("url", "")), ("ID recolector", cfg.get("supabase", {}).get("collectorId", "")), ("Intervalo (s)", str(cfg.get("supabase", {}).get("intervalSeconds", 60))), ("Token (sesión)", os.environ.get("RIEGOBOT_COLLECTOR_TOKEN", ""))]:
            row = tk.Frame(self.content, bg=BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, width=16, anchor="w", bg=BG, fg="#b8cdc2", font=("Segoe UI", 9)).pack(side="left")
            entry = tk.Entry(row, relief="flat", bg="#24413a", fg="white", insertbackground="white", show="•" if label.startswith("Token") else "")
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
        text = tk.Text(self.content, height=8, bg="#203a33", fg="#d4e5d9", font=("Consolas", 8), wrap="word", relief="flat")
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
