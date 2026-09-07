"""Supersampled drawing surface shared by the desktop and visual previews."""
from PIL import Image, ImageDraw, ImageFont
from functools import lru_cache
from .robot import mesh, draw_robot
from . import PROJECT_ROOT


@lru_cache(maxsize=1)
def company_logo():
    with Image.open(PROJECT_ROOT / "assets/branding/camposol-original.jpg") as source:
        return source.convert("RGBA")


@lru_cache(maxsize=1)
def geometry():
    return mesh()


@lru_cache(maxsize=64)
def robot_frame(yaw, blink, phase, color, busy):
    surface = Surface()
    draw_robot(surface, geometry(), 4.7 if blink else 1+phase/4, 0, yaw, color, busy)
    rendered = surface.finish()
    rendered.putalpha(rendered.getchannel("A").point(lambda value: 255 if value >= 128 else 0))
    return rendered


class Surface:
    def __init__(self, width=420, height=280, scale=3):
        self.scale = scale
        self.size = (width, height)
        self.image = Image.new("RGBA", (width*scale, height*scale))
        self.pen = ImageDraw.Draw(self.image)

    def coords(self, values):
        return tuple(v*self.scale for v in values)

    def create_polygon(self, values, fill, **kwargs):
        self.pen.polygon(self.coords(values), fill=fill)

    def create_oval(self, *box, fill=None, outline=None, width=1, **kwargs):
        self.pen.ellipse(self.coords(box), fill=fill or None, outline=outline or None, width=max(1, round(width*self.scale)))

    def create_rectangle(self, *box, fill=None, outline=None, **kwargs):
        self.pen.rounded_rectangle(self.coords(box), radius=2*self.scale, fill=fill or None, outline=outline or None)

    def create_line(self, *values, fill, width=1, **kwargs):
        self.pen.line(self.coords(values), fill=fill, width=max(1, round(width*self.scale)), joint="curve")

    def create_arc(self, *box, start, extent, style=None, outline=None, fill=None, width=1, **kwargs):
        if style == "arc":
            self.pen.arc(self.coords(box), -start-extent, -start, fill=outline, width=max(1, round(width*self.scale)))
        else:
            self.pen.pieslice(self.coords(box), -start-extent, -start, fill=fill, outline=outline or None)

    def create_text(self, x, y, text, fill, font, **kwargs):
        try:
            face = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", round(font[1]*self.scale*1.25))
        except OSError:
            face = ImageFont.load_default(size=round(font[1]*self.scale*1.25))
        self.pen.text(self.coords((x,y)), text, fill=fill, font=face, anchor="mm")

    def brand(self, x, y, size):
        # Display the original artwork intact, including its white margin.
        pixels = round(size*self.scale)
        logo = company_logo().resize((pixels, pixels), Image.Resampling.LANCZOS)
        self.image.alpha_composite(logo, (round((x-size/2)*self.scale), round((y-size/2)*self.scale)))

    def finish(self):
        return self.image.resize(self.size, Image.Resampling.LANCZOS)
