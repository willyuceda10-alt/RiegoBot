"""Single desktop window with a compact companion and keyboard controls."""
from __future__ import annotations

import json
import math
import os
import sys
import time
import tkinter as tk
from tkinter import font as tkfont
from uuid import UUID
from PIL import ImageTk, Image
from . import PROJECT_ROOT
from .config import load_config
from .robot_surface import company_logo
from .companion_art import companion_frame, motion_pose, thought_frame, PALETTES

BG, INK, MUTED, KEY = "#f2f4ed", "#243e2d", "#53654d", "#ff00ff"
COMPACT_W, COMPACT_H, PANEL_W = 230, 210, 420


class CompanionView:
    def setup_view(self, root):
        self.expanded = False
        self.page = None
        self.birth = time.monotonic()
        self.last_motion_at = self.birth
        self.motion_activity = 0.0
        self.drag = None
        self.state_var = tk.StringVar(value=self.status)
        self.info_var = tk.StringVar()
        self.preferences_path = PROJECT_ROOT / "runtime/mascot-ui.json"
        try:
            prefs = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            if not isinstance(prefs, dict):
                prefs = {}
        except (OSError, ValueError):
            prefs = {}
        self.reduced_motion = tk.BooleanVar(value=prefs.get("reducedMotion") is True)
        self.framed = tk.BooleanVar(value=prefs.get("windowFrame") is True)
        self.topmost = tk.BooleanVar(value=prefs.get("topmost", True) is True)
        self.large_text = tk.BooleanVar(value=prefs.get("largeText") is True)
        self.body_font = tkfont.Font(family="Segoe UI", size=12 if self.large_text.get() else 10)
        self.title_font = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        self.mono_font = tkfont.Font(family="Consolas", size=11 if self.large_text.get() else 10)
        # Raster scene is intentionally fixed-size; pixel fonts avoid DPI clipping here.
        self.caption_font = tkfont.Font(family="Segoe UI", size=-14 if self.large_text.get() else -12)
        root.title("RiegoBot · Recolector Dream")
        root.overrideredirect(not self.framed.get())
        root.attributes("-topmost", self.topmost.get())
        root.configure(bg=KEY)
        root.protocol("WM_DELETE_WINDOW", self.close)
        if sys.platform == "win32":
            root.wm_attributes("-transparentcolor", KEY)
        root.geometry(f"230x210+{max(0, root.winfo_screenwidth()-270)}+{max(0, root.winfo_screenheight()-300)}")
        self.canvas = tk.Canvas(root, width=COMPACT_W, height=COMPACT_H, bg=KEY, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.move)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Button-3>", lambda e: self.show_panel())
        root.bind("<Escape>", lambda e: self.collapse())
        root.bind("<Control-Return>", lambda e: self.open_controls())
        root.bind("<MouseWheel>", self.scroll)
        root.bind("<Prior>", lambda e: self.scroll(e, -1))
        root.bind("<Next>", lambda e: self.scroll(e, 1))
        root.bind("<FocusIn>", self.reveal_focus, add="+")
        self.image_item = self.canvas.create_image(0, 0, anchor="nw")
        self.thought_item = self.canvas.create_image(0, 0, anchor="nw")
        # Native action/state, independent of decorative Canvas artwork.
        self.caption_button = tk.Button(self.canvas, text="En espera", command=self.show_panel,
            bg=PALETTES["waiting"]["fill"], fg=PALETTES["waiting"]["ink"],
            activebackground=PALETTES["waiting"]["fill"], activeforeground=INK,
            font=self.caption_font, relief="flat", bd=0, highlightthickness=1, padx=0, pady=0,
            highlightbackground=PALETTES["waiting"]["fill"], highlightcolor=INK, takefocus=True, cursor="hand2")
        self.caption_button.bind("<Return>", lambda e: self.show_panel())
        self.canvas.create_window(121, 19, window=self.caption_button, width=104, height=28)
        # Scroll all controls so high DPI never leaves an action below an inaccessible edge.
        self.controls = tk.Frame(root, bg=BG)
        self.panel_canvas = tk.Canvas(self.controls, bg=BG, highlightthickness=0, width=PANEL_W-24)
        self.panel_scroll = tk.Scrollbar(self.controls, orient="vertical", command=self.panel_canvas.yview)
        self.panel_scroll.pack(side="right", fill="y")
        self.panel_canvas.configure(yscrollcommand=self.panel_scroll.set)
        self.panel_canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.panel_canvas, bg=BG, padx=18, pady=14)
        self.body_window = self.panel_canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: self.panel_canvas.configure(scrollregion=self.panel_canvas.bbox("all")))
        self.panel_canvas.bind("<Configure>", self.fit_body)
        header = tk.Frame(self.body, bg=BG)
        header.pack(fill="x")
        self.logo_image = ImageTk.PhotoImage(company_logo().resize((48, 48), Image.Resampling.LANCZOS))
        tk.Label(header, image=self.logo_image, bg=BG, bd=0).pack(side="left", padx=(0, 12))
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left")
        tk.Label(titles, text="RiegoBot", bg=BG, fg=INK, font=self.title_font).pack(anchor="w")
        self.label(titles, "Recolector Dream · Camposol").pack(anchor="w")
        self.state_label = self.label(self.body, variable=self.state_var, color=INK)
        self.state_label.pack(anchor="w", fill="x", pady=(10, 6))
        self.info_label = self.label(self.body, variable=self.info_var)
        self.info_label.pack(anchor="w", fill="x")
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", pady=8)
        self.run_button = self.button(row, "Iniciar automático", self.toggle_running, accent=True)
        self.sync_button = self.button(row, "Sincronizar ahora", self.once)
        nav = tk.Frame(self.body, bg=BG)
        nav.pack(fill="x")
        for index, (label, action) in enumerate([("Ajustes", self.config), ("Actividad", self.logs), ("Minimizar", self.collapse), ("Salir", self.close)]):
            b = self.button(nav, label, action, pack=False)
            b.grid(row=index//2, column=index%2, sticky="ew", padx=(0, 5), pady=2)
        nav.columnconfigure((0, 1), weight=1)
        self.content = tk.Frame(self.body, bg=BG)
        self.content.pack(fill="both", expand=True)
        self.frame_key = None
        self.draw_state = None
        self.robot_image = None
        self.thought_image = None
        self.animate()

    def label(self, parent, text="", variable=None, color=MUTED):
        return tk.Label(parent, text=text, textvariable=variable, bg=BG, fg=color,
                        font=self.body_font, anchor="w", justify="left", wraplength=340)

    def button(self, parent, label, action, accent=False, pack=True):
        base = "#31563a" if accent else "#e5eade"
        b = tk.Button(parent, text=label, command=action, font=self.body_font,
            bg=base, fg="white" if accent else "#30452e", activebackground="#cbdabe",
            activeforeground=INK, relief="flat", bd=0, padx=10, pady=8, cursor="hand2",
            highlightthickness=2, highlightbackground=BG, highlightcolor=INK, takefocus=True)
        b.bind("<Return>", lambda e: b.invoke())
        b.bind("<Enter>", lambda e: b.configure(bg="#46724b" if accent else "#d8e2cd"))
        b.bind("<Leave>", lambda e: b.configure(bg=base))
        if pack:
            b.pack(anchor="w", fill="x", pady=2)
        return b

    def fit_body(self, event):
        self.panel_canvas.itemconfigure(self.body_window, width=event.width)
        width = max(120, event.width-36)
        self.state_label.configure(wraplength=width)
        self.info_label.configure(wraplength=width)

    def scroll(self, event, pages=None):
        if not self.expanded or isinstance(event.widget, tk.Text):
            return None
        if pages is not None:
            self.panel_canvas.yview_scroll(pages, "pages")
        elif event.delta:
            self.panel_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def reveal_focus(self, event):
        widget = event.widget
        if not self.expanded or not str(widget).startswith(str(self.body)+"."):
            return
        y = widget.winfo_rooty()-self.body.winfo_rooty()
        top = self.panel_canvas.canvasy(0)
        if y < top or y+widget.winfo_height() > top+self.panel_canvas.winfo_height():
            target = y if y < top else y+widget.winfo_height()-self.panel_canvas.winfo_height()
            self.panel_canvas.yview_moveto(max(0, target)/max(1, self.body.winfo_height()))

    def resize(self):
        self.root.update_idletasks()
        scene_left = self.root.winfo_x()+self.canvas.winfo_x()
        scene_top = self.root.winfo_y()+self.canvas.winfo_y()
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width = min(screen_w-16, max(PANEL_W, self.body_font.measure("Recolector Dream · Camposol")+145)) if self.expanded else COMPACT_W
        align_right = scene_left >= width-COMPACT_W
        above = False
        if self.expanded:
            self.panel_canvas.itemconfigure(self.body_window, width=width-41)
            self.root.update_idletasks()
            desired = min(self.body.winfo_reqheight(), 540 if self.page else 460)
            below_space = screen_h-55-scene_top-COMPACT_H
            above_space = scene_top-40
            above = below_space < desired and above_space > below_space
            panel_height = min(desired, max(180, above_space if above else below_space))
            height = min(COMPACT_H+panel_height, screen_h-100)
        else:
            height = COMPACT_H
        x = scene_left+COMPACT_W-width if align_right else scene_left
        x = max(0, min(int(x), screen_w-width))
        y = int(scene_top-(height-COMPACT_H if above else 0))
        y = max(35 if self.framed.get() else 0, min(y, screen_h-height-55))
        self.controls.pack_forget()
        self.canvas.pack_forget()
        self.canvas.pack(side="bottom" if above else "top", anchor="e" if align_right else "w")
        if self.expanded:
            self.controls.pack(fill="both", expand=True, padx=12, side="top")
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.update_idletasks()

    def toggle_running(self):
        self.pause() if self.running else self.start()
        self.draw()

    def open_controls(self):
        self.root.deiconify()
        self.expanded = True
        self.resize()
        self.panel_canvas.yview_moveto(0)
        self.root.lift()
        self.run_button.focus_force()

    def show_panel(self):
        self.collapse() if self.expanded else self.open_controls()

    def collapse(self):
        self.expanded = False
        self.resize()
        self.caption_button.focus_set()

    def press(self, e):
        self.caption_button.focus_set()
        self.drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())

    def move(self, e):
        if self.drag:
            x, y, rx, ry = self.drag
            nx = max(0, min(self.root.winfo_screenwidth()-self.root.winfo_width(), rx+e.x_root-x))
            ny = max(0, min(self.root.winfo_screenheight()-self.root.winfo_height(), ry+e.y_root-y))
            self.root.geometry(f"+{nx}+{ny}")

    def release(self, e):
        if self.drag and abs(e.x_root-self.drag[0])+abs(e.y_root-self.drag[1]) < 6:
            self.show_panel()
        self.drag = None

    def draw(self):
        now = time.monotonic()
        elapsed = max(0, min(.1, now-self.last_motion_at))
        self.last_motion_at = now
        target = 1.0 if self.busy and not self.closing else 0.0
        self.motion_activity += (target-self.motion_activity)*(1-math.exp(-elapsed/0.55))
        key = motion_pose(now-self.birth, self.motion_activity, self.reduced_motion.get())
        if key != self.frame_key:
            frame = companion_frame(key)
            if self.robot_image is None:
                self.robot_image = ImageTk.PhotoImage(frame)
                self.canvas.itemconfigure(self.image_item, image=self.robot_image)
            else:
                self.robot_image.paste(frame)
            self.frame_key = key
        indicator = self.visual_status(now)
        state = (self.busy, self.running, self.closing, self.status_kind, indicator)
        if state != self.draw_state:
            self.run_button.configure(text="Pausar automático" if self.running else "Iniciar automático", state="disabled" if self.closing else "normal")
            self.sync_button.configure(state="disabled" if self.busy or self.closing else "normal")
            caption = {"waiting": "Leyendo…" if self.busy else "En espera",
                       "online": "En línea", "error": "Revisar fallo"}[indicator]
            palette = PALETTES[indicator]
            self.caption_button.configure(text=caption, bg=palette["fill"], fg=palette["ink"],
                activebackground=palette["fill"], activeforeground=palette["ink"],
                highlightbackground=palette["fill"], highlightcolor=palette["ink"])
            if self.thought_image is None:
                self.thought_image = ImageTk.PhotoImage(thought_frame(indicator))
                self.canvas.itemconfigure(self.thought_item, image=self.thought_image)
            else:
                self.thought_image.paste(thought_frame(indicator))
            self.draw_state = state

    def animate(self):
        started = time.monotonic()
        self.draw()
        interval = 500 if self.reduced_motion.get() else max(8, 33-round((time.monotonic()-started)*1000))
        self.animation_timer = self.root.after(interval, self.animate)

    def clear_content(self, page):
        for widget in self.content.winfo_children():
            widget.destroy()
        self.page = page
        if page:
            self.button(self.content, "‹ Volver al estado", lambda: self.clear_content(None))
        self.resize()
        if not page:
            self.panel_canvas.yview_moveto(0)
            self.run_button.focus_set()

    def save_preferences(self):
        prefs = {"reducedMotion": self.reduced_motion.get(), "windowFrame": self.framed.get(),
                 "topmost": self.topmost.get(), "largeText": self.large_text.get()}
        self.root.overrideredirect(not self.framed.get())
        self.root.attributes("-topmost", self.topmost.get())
        self.body_font.configure(size=12 if self.large_text.get() else 10)
        self.mono_font.configure(size=11 if self.large_text.get() else 10)
        self.caption_font.configure(size=-14 if self.large_text.get() else -12)
        try:
            self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.preferences_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(prefs), encoding="utf-8")
            temporary.replace(self.preferences_path)
        except OSError:
            self.set_status("La preferencia se aplicó, pero no pudo guardarse.", "#c36a47", "error")
        self.resize()
        self.draw()

    def config(self):
        self.clear_content("config")
        self.label(self.content, "Comodidad y accesibilidad", color=INK).pack(anchor="w", pady=(10, 4))
        checks = []
        for text, variable in [("Reducir movimiento", self.reduced_motion), ("Texto grande", self.large_text),
                               ("Siempre visible", self.topmost), ("Barra de título y acceso con Alt+Tab", self.framed)]:
            check = tk.Checkbutton(self.content, text=text, variable=variable, command=self.save_preferences,
                bg=BG, fg=INK, activebackground=BG, activeforeground=INK, selectcolor="white",
                font=self.body_font, anchor="w", takefocus=True, highlightthickness=2,
                highlightbackground=BG, highlightcolor=INK, wraplength=310)
            check.pack(fill="x", pady=2)
            checks.append(check)
        self.label(self.content, "Pulsa el pensamiento o Enter para abrir controles. Escape minimiza; Tab recorre acciones.").pack(fill="x", pady=8)
        try:
            cfg = load_config(PROJECT_ROOT)
        except (OSError, ValueError):
            self.set_status("No se pudo leer la configuración local. Revisa su formato y permisos.", "#c36a47", "config")
            self.resize()
            return
        self.entries = {}
        for label, value in [("Carpeta Dream", cfg.get("discovery", {}).get("rootPath", "")), ("URL Supabase", cfg.get("supabase", {}).get("url", "")), ("ID recolector", cfg.get("supabase", {}).get("collectorId", "")), ("Intervalo (s)", str(cfg.get("supabase", {}).get("intervalSeconds", 60))), ("Token (sesión)", os.environ.get("RIEGOBOT_COLLECTOR_TOKEN", ""))]:
            self.label(self.content, label).pack(anchor="w", pady=(6, 2))
            entry = tk.Entry(self.content, relief="flat", bg="white", fg=INK, insertbackground=INK,
                font=self.body_font, highlightthickness=2, highlightcolor=INK,
                highlightbackground="#cbd4c4", show="•" if label.startswith("Token") else "")
            entry.insert(0, value)
            entry.pack(fill="x", ipady=5)
            self.entries[label] = entry
        self.config_error = tk.StringVar()
        self.label(self.content, variable=self.config_error, color="#96391f").pack(fill="x", pady=4)
        self.button(self.content, "Guardar ajustes", self.save_config, accent=True)
        self.resize()
        checks[0].focus_set()

    def save_config(self):
        if self.busy:
            self.config_error.set("Espera a que termine el ciclo antes de cambiar la conexión.")
            return
        current = None
        try:
            from .collector import ingest_endpoint
            current = self.entries["Intervalo (s)"]
            interval = int(current.get())
            if not 30 <= interval <= 86400:
                raise ValueError("Invalid interval")
            current = self.entries["URL Supabase"]
            url = current.get().strip().rstrip("/")
            ingest_endpoint(url)
            current = self.entries["ID recolector"]
            collector_id = str(UUID(current.get().strip()))
            current = self.entries["Carpeta Dream"]
            dream_path = current.get().strip()
            if not dream_path:
                raise ValueError("Missing folder")
            path = PROJECT_ROOT / "config/config.local.json"
            local = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            local.setdefault("discovery", {})["rootPath"] = dream_path
            local.setdefault("supabase", {}).update(url=url, collectorId=collector_id, intervalSeconds=interval)
            local["readOnly"] = True
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(local, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            temporary.replace(path)
            os.environ["RIEGOBOT_COLLECTOR_TOKEN"] = self.entries["Token (sesión)"].get().strip()
            self.invalidate_connection()
            self.config_error.set("Guardado. El token permanece solo en esta sesión.")
            self.set_status("Ajustes guardados. Puedes iniciar la lectura.", "#63ab65", "ready")
        except (ValueError, OSError, AttributeError, TypeError):
            messages = {"Intervalo (s)": "Indica un intervalo entero entre 30 y 86400 segundos.",
                        "URL Supabase": "Indica el origen HTTPS de Supabase, sin usuario, contraseña ni rutas.",
                        "ID recolector": "Indica un ID de recolector UUID válido.",
                        "Carpeta Dream": "Revisa la carpeta y el archivo de configuración local."}
            label = next((label for label, entry in self.entries.items() if entry is current), "Carpeta Dream")
            self.config_error.set(messages[label])
            if current:
                current.focus_set()
        self.resize()

    def logs(self):
        self.clear_content("logs")
        text = tk.Text(self.content, height=10, bg="white", fg=INK, font=self.mono_font,
                       wrap="word", relief="flat", highlightthickness=2, highlightcolor=INK)
        text.pack(fill="both", expand=True, pady=7)
        path = PROJECT_ROOT / "runtime/mascot.log"
        try:
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size-10000))
                content = stream.read(10000).decode("utf-8", errors="replace")
        except FileNotFoundError:
            content = "Todavía no hay ciclos registrados."
        except OSError:
            content = "No se pudo abrir el registro. Revisa los permisos del archivo."
        token = os.environ.get("RIEGOBOT_COLLECTOR_TOKEN")
        if token:
            content = content.replace(token, "[token oculto]")
        text.insert("1.0", content)
        text.see("end")
        text.configure(state="disabled")
        self.resize()
        text.focus_set()
