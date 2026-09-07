"""Compact four-pose desk companion; original art is preserved."""
from collections import deque
from functools import lru_cache
from PIL import Image, ImageDraw
from . import PROJECT_ROOT
from .robot_surface import company_logo


def cutout(frame):
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
    return frame


@lru_cache(maxsize=1)
def sprites():
    with Image.open(PROJECT_ROOT / "assets/mascot/desk-sheet.png") as source:
        w,h = source.width//2, source.height//2
        frames = [cutout(source.crop(((index%2)*w,(index//2)*h,(index%2+1)*w,(index//2+1)*h)).convert("RGBA")) for index in range(4)]
    base = frames[0].getchannel("A").getbbox()
    aligned=[]
    for frame in frames:
        bounds=frame.getchannel("A").getbbox()
        if not bounds: raise ValueError("Empty desk sprite")
        dx,dy=base[0]-bounds[0],base[3]-bounds[3]
        canvas=Image.new("RGBA",(w,h))
        canvas.alpha_composite(frame,(dx,dy))
        aligned.append(canvas)
    boxes=[frame.getchannel("A").getbbox() for frame in aligned]
    common=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
    result=[]
    for frame in aligned:
        # The supplied logo is placed on the desk's blank circular badge.
        logo=company_logo().resize((36,44),Image.Resampling.LANCZOS)
        alpha=Image.new("L",logo.size)
        ImageDraw.Draw(alpha).ellipse((0,0,35,43),fill=255)
        logo.putalpha(alpha)
        frame.alpha_composite(logo,(401,412))
        frame=frame.crop(common)
        frame.thumbnail((222,178),Image.Resampling.LANCZOS)
        result.append(frame)
    return tuple(result)


@lru_cache(maxsize=16)
def companion_frame(phase: int, blink: bool, busy: bool):
    frame = sprites()[3 if blink else phase%3]
    result=Image.new("RGBA",(230,210))
    result.alpha_composite(frame,((230-frame.width)//2,180-frame.height))
    # Connection indicator is separate from decorative typing; it reflects real work.
    draw=ImageDraw.Draw(result)
    draw.rounded_rectangle((142,16,224,35),radius=6,fill="#eaf0e4",outline="#ccd9c3")
    color="#659c49" if busy else "#a4ac9e"
    draw.ellipse((149,23,154,28),fill=color)
    from PIL import ImageFont
    try:font=ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf",10)
    except OSError:font=ImageFont.load_default()
    draw.text((159,20),"DREAM" if busy else "En espera",font=font,fill="#35503a")
    if busy:
        for i in range(3):
            draw.rectangle((157+i*8,31,161+i*8,32),fill="#90b673" if i==phase%3 else "#d0ddc8")
    result.putalpha(result.getchannel("A").point(lambda value:255 if value>=128 else 0))
    return result
