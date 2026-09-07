"""Compact desk companion loaded from a prepared, four-pose RGBA atlas."""
from functools import lru_cache
from PIL import Image, ImageDraw
from . import PROJECT_ROOT


@lru_cache(maxsize=1)
def sprites():
    path = PROJECT_ROOT / "assets/mascot/desk-sprites.png"
    with Image.open(path) as source:
        if source.mode != "RGBA" or source.width % 2 or source.height % 2:
            raise ValueError("Invalid companion atlas; run python scripts/prepare_companion.py.")
        width, height = source.width // 2, source.height // 2
        if not width or not height or width > 222 or height > 178:
            raise ValueError("Unexpected companion atlas dimensions.")
        frames = tuple(
            source.crop((
                (index % 2) * width,
                (index // 2) * height,
                (index % 2 + 1) * width,
                (index // 2 + 1) * height,
            ))
            for index in range(4)
        )
    if any(frame.getchannel("A").getbbox() is None for frame in frames):
        raise ValueError("The companion atlas contains an empty pose.")
    return frames


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
