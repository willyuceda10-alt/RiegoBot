"""Display adapter for the illustrated companion. Original artwork stays intact."""
from collections import deque
from functools import lru_cache

from PIL import Image, ImageDraw

from . import PROJECT_ROOT
from .robot_surface import company_logo


@lru_cache(maxsize=2)
def sprite(blink: bool):
    with Image.open(PROJECT_ROOT / "assets/mascot/technician-sheet.png") as source:
        half = source.width // 2
        frame = source.crop((half if blink else 0, 0, source.width if blink else half, source.height)).convert("RGBA")
    # The generator exported an opaque preview grid. The desktop display clips
    # only its light neutral exterior, preserving enclosed eye/garment highlights.
    # This is an in-memory display mask; the delivered artwork is never changed.
    width, height = frame.size
    pixels = frame.load()
    visited = bytearray(width*height)
    boundary = deque()
    def add(x, y):
        index = y*width+x
        if visited[index]:
            return
        visited[index] = 1
        red, green, blue, _ = pixels[x,y]
        if min(red,green,blue) >= 226 and max(red,green,blue)-min(red,green,blue) <= 14:
            boundary.append((x,y))
            pixels[x,y] = (red,green,blue,0)
    for x in range(width):
        add(x,0); add(x,height-1)
    for y in range(height):
        add(0,y); add(width-1,y)
    while boundary:
        x,y = boundary.popleft()
        if x: add(x-1,y)
        if x+1<width: add(x+1,y)
        if y: add(x,y-1)
        if y+1<height: add(x,y+1)
    # Place the exact supplied brand inside the illustrated blank uniform patch.
    logo = company_logo().resize((30,30), Image.Resampling.LANCZOS)
    alpha = Image.new("L", (30,30))
    ImageDraw.Draw(alpha).ellipse((0,0,29,29), fill=255)
    logo.putalpha(alpha)
    badge_x = 378 if blink else 422
    frame.alpha_composite(logo, (badge_x-15, 290))
    bounds = frame.getchannel("A").getbbox()
    if not bounds:
        raise ValueError("El recurso de la mascota está vacío")
    frame = frame.crop(bounds)
    frame.thumbnail((290,294),Image.Resampling.LANCZOS)
    return frame


@lru_cache(maxsize=16)
def companion_frame(lean: float, blink: bool):
    frame = sprite(blink)
    # Very limited tilt: stable posture, no constant rocking of the entire UI.
    if lean:
        frame = frame.rotate(-lean, Image.Resampling.BICUBIC, expand=True)
    result = Image.new("RGBA", (420,340))
    result.alpha_composite(frame, ((420-frame.width)//2, 304-frame.height))
    # Native Windows color-key windows need binary alpha at their boundary.
    result.putalpha(result.getchannel("A").point(lambda value: 255 if value>=128 else 0))
    return result
