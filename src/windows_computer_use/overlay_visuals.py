"""Border and fading point animation, rendered only in narrow screen-edge strips."""

import io
import math
import random
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

import resvg_py
from PIL import Image, ImageDraw, ImageFilter

HEADLINE = "Antigravity is using your computer"
BORDER_WIDTH = 68
EDGE_WIDTH = 132
PARTICLE_COUNT = 144
BORDER_RGB = (249, 62, 78)
FRAME_MS = 42
PULSE_PERIOD = 3.2
PULSE_GROWTH = 32
PULSE_STEPS = 16
ACTIVITIES = {
    "ready": "Listo para continuar",
    "reading": "Leyendo la pantalla",
    "inspecting": "Leyendo controles de la ventana",
    "interacting": "Interactuando con la pantalla",
}


def subtitle(state):
    activity = ACTIVITIES.get(state.get("activity"), ACTIVITIES["ready"])
    project = str(state.get("project_name") or "").strip()
    if project:
        activity += " · " + (project[:31] + "…" if len(project) > 32 else project)
    return activity


@lru_cache(maxsize=16)
def brand_image(name, size):
    if name not in {"antigravity", "antigravity-white", "gemini"}:
        raise ValueError("Unknown packaged brand asset")
    svg = files("windows_computer_use").joinpath("assets", name + ".svg").read_text("utf-8")
    png = resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def edge_boxes(width, height, scale=1.0):
    band = min(round(EDGE_WIDTH * scale), width // 2, height // 2)
    return [
        (0, 0, width, band),
        (0, height - band, width, height),
        (0, band, band, height - band),
        (width - band, band, width, height - band),
    ]


def heartbeat(now):
    """Two soft beats followed by a quiet interval, independent of frame rate."""
    phase = now % PULSE_PERIOD
    return min(
        1.0,
        math.exp(-(((phase - 0.45) / 0.24) ** 2))
        + 0.55 * math.exp(-(((phase - 1.05) / 0.28) ** 2)),
    )


def _border_surface(width, height, scale, pulse, box):
    # Draw only a padded edge strip; the padding keeps blur continuous at seams.
    pad = math.ceil(27 * scale)
    left, top, right, bottom = box
    image = Image.new("RGBA", (right - left + pad * 2, bottom - top + pad * 2))
    draw = ImageDraw.Draw(image)
    thickness = max(1, round((BORDER_WIDTH + PULSE_GROWTH * pulse) * scale))
    for inset in range(thickness):
        progress = inset / max(1, thickness - 1)
        alpha = round((112 + 32 * pulse) * (1 - progress) ** 1.15 + 4)
        draw.rectangle(
            (
                inset - left + pad,
                inset - top + pad,
                width - inset - 1 - left + pad,
                height - inset - 1 - top + pad,
            ),
            outline=(*BORDER_RGB, alpha),
        )
    halo = image.filter(ImageFilter.GaussianBlur(9 * scale))
    halo.putalpha(halo.getchannel("A").point(lambda alpha: round(alpha * 0.3)))
    return Image.alpha_composite(halo, image).crop(
        (pad, pad, image.width - pad, image.height - pad)
    )


def border_image(width, height, scale=1.0, pulse=0.0):
    return _border_surface(width, height, scale, max(0.0, min(1.0, pulse)), (0, 0, width, height))


@lru_cache(maxsize=512)
def point_sprite(radius, alpha, color, sparkle=False):
    pad = max(5, radius * 4)
    size = pad * 2 + 1
    glow = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(glow)
    draw.ellipse(
        (pad - radius * 2, pad - radius * 2, pad + radius * 2, pad + radius * 2),
        fill=(*color, alpha // 2),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(max(1, radius * 1.5)))
    ImageDraw.Draw(glow).ellipse(
        (pad - radius, pad - radius, pad + radius, pad + radius), fill=(*color, alpha)
    )
    if sparkle:
        draw = ImageDraw.Draw(glow)
        reach = max(3, radius * 3)
        draw.line((pad - reach, pad, pad + reach, pad), fill=(*color, alpha // 2), width=1)
        draw.line((pad, pad - reach, pad, pad + reach), fill=(*color, alpha // 2), width=1)
    return glow


@dataclass
class Point:
    x: float
    y: float
    dx: float
    dy: float
    born: float
    life: float
    radius: int
    color: tuple
    sparkle: bool


class EdgeAnimation:
    def __init__(self, width, height, scale=1.0, seed=0):
        self.width, self.height, self.scale = width, height, scale
        self.boxes = edge_boxes(width, height, scale)
        self.pulse_backgrounds = [
            [_border_surface(width, height, scale, step / PULSE_STEPS, box) for box in self.boxes]
            for step in range(PULSE_STEPS + 1)
        ]
        self.backgrounds = self.pulse_backgrounds[0]
        self.random = random.Random(seed)
        self.points = []

    def spawn(self, now):
        rng, scale = self.random, self.scale
        # Select edges in proportion to their length. Keep every dot near an edge.
        side = rng.choices(range(4), weights=(self.width, self.width, self.height, self.height))[0]
        offset = rng.uniform(5, 66) * scale
        if side < 2:
            x, y = (
                rng.uniform(24 * scale, self.width - 24 * scale),
                offset if side == 0 else self.height - offset,
            )
            dx, dy = rng.uniform(-7, 7) * scale, rng.uniform(-1, 1) * scale
        else:
            x, y = (
                offset if side == 2 else self.width - offset,
                rng.uniform(24 * scale, self.height - 24 * scale),
            )
            dx, dy = rng.uniform(-1, 1) * scale, rng.uniform(-7, 7) * scale
        return Point(
            x,
            y,
            dx,
            dy,
            now,
            rng.uniform(2.2, 5.5),
            max(1, round(rng.uniform(0.6, 1.8) * scale)),
            rng.choice(((255, 220, 224), (216, 204, 255), (255, 145, 152))),
            rng.random() < 0.23,
        )

    def frames(self, now):
        if not self.points:
            self.points = [
                self.spawn(now - self.random.uniform(0, 2)) for _ in range(PARTICLE_COUNT)
            ]
        self.points = [p if now - p.born < p.life else self.spawn(now) for p in self.points]
        position = heartbeat(now) * PULSE_STEPS
        lower = min(PULSE_STEPS - 1, int(position))
        frames = [
            Image.blend(a, b, position - lower)
            for a, b in zip(self.pulse_backgrounds[lower], self.pulse_backgrounds[lower + 1])
        ]
        for point in self.points:
            age = max(0, now - point.born)
            alpha = round(200 * math.sin(math.pi * min(1, age / point.life)) ** 2)
            alpha = round(alpha / 16) * 16
            if alpha < 16:
                continue
            sprite = point_sprite(point.radius, min(255, alpha), point.color, point.sparkle)
            x, y = point.x + point.dx * age, point.y + point.dy * age
            half = sprite.width // 2
            for frame, (left, top, right, bottom) in zip(frames, self.boxes):
                if left - half <= x < right + half and top - half <= y < bottom + half:
                    frame.alpha_composite(sprite, (round(x - left) - half, round(y - top) - half))
        return frames


class CursorAnimation:
    """A translucent halo and short point trail; never replace the system cursor."""

    def __init__(self, scale=1.0):
        self.scale = scale
        self.size = round(112 * scale)
        self.center = self.size // 2
        self.history = []
        self.last_pressed = False
        self.clicked_at = -10.0

    def frame(self, x, y, now, pressed=False):
        if pressed and not self.last_pressed:
            self.clicked_at = now
        self.last_pressed = pressed
        self.history.append((x, y, now))
        self.history = [sample for sample in self.history[-14:] if now - sample[2] < 0.35]
        image = Image.new("RGBA", (self.size, self.size))
        center, scale = self.center, self.scale
        for old_x, old_y, born in self.history[:-1]:
            age = (now - born) / 0.35
            opacity = round(100 * (1 - age))
            dot = point_sprite(max(1, round(1.2 * scale)), opacity, (186, 183, 255))
            image.alpha_composite(
                dot,
                (
                    round(center + old_x - x - dot.width / 2),
                    round(center + old_y - y - dot.height / 2),
                ),
            )
        draw = ImageDraw.Draw(image)
        for radius in range(round(23 * scale), round(9 * scale), -1):
            alpha = round(22 * (1 - radius / (25 * scale)))
            draw.ellipse(
                (center - radius, center - radius, center + radius, center + radius),
                outline=(146, 171, 255, alpha),
                width=max(1, round(2 * scale)),
            )
        radius = round(12 * scale)
        draw.ellipse(
            (center - radius, center - radius, center + radius, center + radius),
            outline=(195, 204, 255, 115),
            width=max(1, round(scale)),
        )
        pulse = now - self.clicked_at
        if 0 <= pulse < 0.45:
            radius = round((12 + 24 * pulse / 0.45) * scale)
            draw.ellipse(
                (center - radius, center - radius, center + radius, center + radius),
                outline=(198, 197, 255, round(170 * (1 - pulse / 0.45))),
                width=max(1, round(2 * scale)),
            )
        badge = round(18 * scale)
        bx, by = center + round(17 * scale), center + round(19 * scale)
        draw.rectangle((bx - 3, by - 3, bx + badge + 3, by + badge + 3), fill=(25, 28, 39, 150))
        image.alpha_composite(brand_image("antigravity", badge), (bx, by))
        return image
