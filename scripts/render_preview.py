"""Render a shareable animation preview without capturing personal desktop content."""

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from windows_computer_use.overlay_visuals import (
    HEADLINE,
    CursorAnimation,
    EdgeAnimation,
    brand_image,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    width, height = 960, 540
    background = Image.new("RGBA", (width, height), "#222631")
    draw = ImageDraw.Draw(background)
    for y in range(height):
        shade = round(30 + 9 * y / height)
        draw.line((0, y, width, y), fill=(shade, shade + 3, shade + 10, 255))
    fonts = Path("C:/Windows/Fonts")
    main_font = ImageFont.truetype(str(fonts / "seguisb.ttf"), 15)
    small_font = ImageFont.truetype(str(fonts / "segoeui.ttf"), 11)
    draw.text(
        (width // 2, height // 2),
        "Desktop activity indicator",
        font=main_font,
        fill="#8992a7",
        anchor="mm",
    )
    draw.rectangle((0, height - 38, width, height), fill="#191c24")
    for i, color in enumerate(("#7db8ff", "#899bd6", "#f1cb66", "#c59de2", "#b0becf")):
        draw.rectangle(
            (width // 2 - 76 + i * 34, height - 28, width // 2 - 58 + i * 34, height - 10),
            fill=color,
        )
    bar = Image.new("RGBA", background.size)
    d = ImageDraw.Draw(bar)
    left, top, right, bottom = 140, 104, 820, 172
    d.rectangle((left, top, right, bottom), fill=(25, 28, 37, 227), outline=(56, 62, 76, 190))
    bar.alpha_composite(brand_image("antigravity", 34), (left + 18, top + 17))
    d.text((left + 66, top + 13), HEADLINE, fill="#f4f5fa", font=main_font)
    d.text(
        (left + 66, top + 38), "Leyendo la pantalla · Mi proyecto", fill="#b3bacb", font=small_font
    )
    bar.alpha_composite(brand_image("gemini", 20), (right - 203, top + 24))
    d.text((right - 180, top + 26), "Gemini", fill="#cbd1df", font=small_font)
    d.line((right - 120, top + 14, right - 120, bottom - 14), fill="#3a404e")
    d.rectangle((right - 104, top + 12, right - 18, top + 43), fill="#363d4c")
    d.text((right - 61, top + 27), "■ Detener", anchor="mm", fill="white", font=small_font)
    d.text((right - 61, top + 53), "Ctrl+Alt+Esc", anchor="mm", fill="#9099ae", font=small_font)
    animation = EdgeAnimation(width, height, scale=0.85, seed=12)
    cursor = CursorAnimation(scale=0.85)
    frames = []
    for index in range(80):
        frame = background.copy()
        for strip, (x, y, _, _) in zip(animation.frames(index / 24), animation.boxes):
            frame.alpha_composite(strip, (x, y))
        frame.alpha_composite(bar)
        mouse_x = round(width * 0.52 + 200 * math.sin(index / 80 * math.tau))
        mouse_y = round(height * 0.61 + 70 * math.cos(index / 80 * math.tau))
        halo = cursor.frame(mouse_x, mouse_y, index / 24, pressed=35 <= index <= 38)
        frame.alpha_composite(halo, (mouse_x - cursor.center, mouse_y - cursor.center))
        ImageDraw.Draw(frame).polygon(
            [
                (mouse_x, mouse_y),
                (mouse_x, mouse_y + 20),
                (mouse_x + 5, mouse_y + 15),
                (mouse_x + 10, mouse_y + 24),
                (mouse_x + 14, mouse_y + 22),
                (mouse_x + 9, mouse_y + 13),
                (mouse_x + 18, mouse_y + 13),
            ],
            fill="white",
            outline="#283047",
        )
        frames.append(frame.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=42,
        loop=0,
        optimize=True,
        disposal=1,
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()
