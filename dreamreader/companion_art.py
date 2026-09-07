"""A stable desk illustration with small, continuous character gestures."""
from dataclasses import dataclass
from functools import lru_cache
import math
from PIL import Image, ImageDraw, ImageFilter
from . import PROJECT_ROOT

CANVAS_SIZE = (230, 210)
# Leave space above the head; the compact window keeps its original dimensions.
SCENE_SIZE = (129, 169)
SCENE_POSITION = (50, 39)
PAD = 4
PALETTES = {
    "waiting": {"fill": "#fff0ce", "ink": "#704306", "edge": "#bc7b12", "dot": "#b97308"},
    "online": {"fill": "#e4f3e3", "ink": "#20512c", "edge": "#4b9055", "dot": "#25823b"},
    "error": {"fill": "#ffe8e4", "ink": "#8d2925", "edge": "#c05348", "dot": "#c03732"},
}


@lru_cache(maxsize=1)
def sprites():
    path = PROJECT_ROOT / "assets/mascot/desk-sprites.png"
    with Image.open(path) as source:
        if source.mode != "RGBA" or source.width % 2 or source.height % 2:
            raise ValueError("Invalid companion atlas; run python scripts/prepare_companion.py.")
        width, height = source.width // 2, source.height // 2
        if not width or not height or width > 222 or height > 178:
            raise ValueError("Unexpected companion atlas dimensions.")
        frames = tuple(source.crop(((i % 2)*width, (i//2)*height,
                                    (i % 2+1)*width, (i//2+1)*height)) for i in range(4))
    if any(frame.getchannel("A").getbbox() is None for frame in frames):
        raise ValueError("The companion atlas contains an empty pose.")
    return frames


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value*value*(3-2*value)


def blink_amount(t):
    # Two unequal intervals, with fast closing and slower reopening.
    for start, duration in ((3.1, .27), (8.4, .32)):
        elapsed = t % 12.7-start
        if 0 <= elapsed < duration:
            if elapsed < .09:
                return smoothstep(elapsed/.09)
            if elapsed < .12:
                return 1.0
            return 1-smoothstep((elapsed-.12)/(duration-.12))
    return 0.0


@dataclass(frozen=True)
class MotionPose:
    head_x: float = 0
    head_y: float = 0
    breath: float = 0
    left_tap: float = 0
    right_tap: float = 0
    blink: float = 0


def motion_pose(t, activity=0.0, reduced=False):
    if reduced:
        return MotionPose()
    activity = max(0, min(1, activity))
    # Typing occurs in brief phrases followed by a reading pause. Nothing jumps
    # when a cycle starts: the view eases activity while all clocks keep running.
    phrase = t % 5.8
    envelope = smoothstep(phrase/.65)*(1-smoothstep((phrase-3.6)/.8))
    values = (
        .48*math.sin(t*math.tau/8.9),
        .55*math.sin(t*math.tau/6.4)+.14*math.sin(t*math.tau/11.3),
        .38*math.sin(t*math.tau/4.8),
        activity*envelope*.80*(.5-.5*math.cos(t*math.tau*1.8)),
        activity*envelope*.65*(.5-.5*math.cos(t*math.tau*2.1+.8)),
        blink_amount(t),
    )
    return MotionPose(*(round(value, 4) for value in values))


@lru_cache(maxsize=1)
def rig_assets():
    base = sprites()[0]
    closed = sprites()[3]
    # Use only the eyelids from the alternate pose. Hair, desk and PC never swap.
    mask = Image.new("L", base.size)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((22, 31, 35, 43), fill=255)
    draw.ellipse((37, 30, 48, 42), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(.65))
    shut = Image.composite(closed, base, mask)
    padded = []
    for frame in (base, shut):
        canvas = Image.new("RGBA", (base.width+PAD*2, base.height+PAD*2))
        canvas.paste(frame, (PAD, PAD))
        padded.append(canvas)
    # Spatial weights are prepared once, not recomputed at animation frame rate.
    def vertex(x, y):
        sx, sy = x-PAD, y-PAD
        head = (1-smoothstep((sx-48)/14))*(1-smoothstep((sy-46)/18))
        torso = (1-smoothstep((sx-51)/14))*smoothstep((sy-43)/19)*(1-smoothstep((sy-82)/12))
        def hand(cx, cy, rx, ry):
            distance = ((sx-cx)/rx)**2+((sy-cy)/ry)**2
            return (1-smoothstep(distance)) if distance < 1 else 0
        return (x, y, head, torso, hand(27, 86, 16, 9), hand(59, 85, 10, 8))
    patches = []
    for y in range(0, 100, 5):
        for x in range(0, 75, 5):
            patches.append(((x, y, x+5, y+5), tuple(vertex(a, b) for a, b in
                ((x,y), (x,y+5), (x+5,y+5), (x+5,y)))))
    return padded[0], padded[1], tuple(patches)


def companion_frame(pose: MotionPose):
    """Render one frame; the caller reuses its Tk image instead of caching time."""
    base, shut, patches = rig_assets()
    source = Image.blend(base, shut, pose.blink) if pose.blink else base
    frame = source.copy()
    if any((pose.head_x, pose.head_y, pose.breath, pose.left_tap, pose.right_tap)):
        mesh = []
        for box, vertices in patches:
            quad = []
            for x, y, head, torso, left, right in vertices:
                dx = pose.head_x*head
                dy = pose.head_y*head-pose.breath*torso-pose.left_tap*left-pose.right_tap*right
                quad.extend((x-dx, y-dy))
            mesh.append((box, tuple(quad)))
        # Premultiplied alpha prevents dark fringes at subpixel silhouette motion.
        patch = source.convert("RGBa").transform((75, 100), Image.Transform.MESH,
            mesh, Image.Resampling.BICUBIC).convert("RGBA")
        frame.paste(patch, (0, 0))
    frame = frame.resize((SCENE_SIZE[0]+PAD*2, SCENE_SIZE[1]+PAD*2), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", CANVAS_SIZE)
    result.alpha_composite(frame, (SCENE_POSITION[0]-PAD, SCENE_POSITION[1]-PAD))
    # Windows color-key transparency needs fully transparent exterior pixels.
    result.putalpha(result.getchannel("A").point(lambda value: 255 if value >= 128 else 0))
    return result


@lru_cache(maxsize=3)
def thought_frame(state):
    palette = PALETTES[state]
    scale = 3
    mask = Image.new("L", (CANVAS_SIZE[0]*scale, CANVAS_SIZE[1]*scale))
    draw = ImageDraw.Draw(mask)
    def ellipse(box):
        draw.ellipse(tuple((v+(2 if i % 2 else 0))*scale for i, v in enumerate(box)), fill=255)
    draw.rounded_rectangle((45*scale, 5*scale, 184*scale, 34*scale), radius=10*scale, fill=255)
    for box in ((53,1,83,27), (76,0,115,27), (106,1,144,27), (137,3,172,29),
                (62,33,68,39), (57,42,60,45)):
        ellipse(box)
    outline = mask.filter(ImageFilter.MaxFilter(7))
    result = Image.new("RGBA", mask.size)
    result.paste(palette["edge"], (0, 0), outline)
    result.paste(palette["fill"], (0, 0), mask)
    dot = ImageDraw.Draw(result)
    dot.ellipse((54*scale, 15*scale, 60*scale, 21*scale), fill=palette["dot"])
    result = result.resize(CANVAS_SIZE, Image.Resampling.LANCZOS)
    result.putalpha(result.getchannel("A").point(lambda value: 255 if value >= 128 else 0))
    return result
