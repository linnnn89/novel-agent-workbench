from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "novel_agent_workbench" / "assets"
PNG_PATH = ASSETS / "novel_agent_workbench_icon_1024.png"
ICO_PATH = ASSETS / "novel_agent_workbench.ico"
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def rounded_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def build_icon(size: int = 1024) -> Image.Image:
    scale = size / 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)

    def xy(values: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return tuple(int(v * scale) for v in values)  # type: ignore[return-value]

    sdraw.rounded_rectangle(xy((248, 116, 736, 840)), radius=int(46 * scale), fill=(26, 39, 64, 64))
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(18 * scale)))
    image.alpha_composite(shadow, (0, int(16 * scale)))

    draw = ImageDraw.Draw(image)
    page = xy((230, 96, 716, 820))
    rounded_rect(draw, page, int(42 * scale), "#fffdf8", "#d7dce8", int(8 * scale))

    fold = [
        (int(602 * scale), int(96 * scale)),
        (int(716 * scale), int(210 * scale)),
        (int(602 * scale), int(210 * scale)),
    ]
    draw.polygon(fold, fill="#eef2fb", outline="#d7dce8")
    draw.line(xy((602, 96, 602, 210)), fill="#d7dce8", width=int(6 * scale))

    for y in [300, 380, 460, 540, 620]:
        draw.line(xy((306, y, 640, y)), fill="#e8edf6", width=max(2, int(5 * scale)))

    pen_shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pshadow = ImageDraw.Draw(pen_shadow)
    pshadow.line(
        [(int(612 * scale), int(692 * scale)), (int(824 * scale), int(480 * scale))],
        fill=(26, 39, 64, 58),
        width=int(78 * scale),
    )
    pen_shadow = pen_shadow.filter(ImageFilter.GaussianBlur(int(12 * scale)))
    image.alpha_composite(pen_shadow, (0, int(8 * scale)))

    draw = ImageDraw.Draw(image)
    draw.line(
        [(int(590 * scale), int(690 * scale)), (int(810 * scale), int(470 * scale))],
        fill="#243247",
        width=int(66 * scale),
    )
    draw.line(
        [(int(610 * scale), int(670 * scale)), (int(790 * scale), int(490 * scale))],
        fill="#40516a",
        width=int(24 * scale),
    )
    draw.polygon(
        [
            (int(542 * scale), int(738 * scale)),
            (int(592 * scale), int(634 * scale)),
            (int(650 * scale), int(692 * scale)),
        ],
        fill="#f1c45b",
        outline="#7a6230",
    )
    draw.polygon(
        [
            (int(528 * scale), int(768 * scale)),
            (int(542 * scale), int(738 * scale)),
            (int(564 * scale), int(758 * scale)),
        ],
        fill="#232323",
    )
    draw.line(
        [(int(548 * scale), int(736 * scale)), (int(620 * scale), int(666 * scale))],
        fill="#7a6230",
        width=max(2, int(5 * scale)),
    )
    draw.rounded_rectangle(xy((776, 424, 862, 510)), radius=int(26 * scale), fill="#dfe6f2", outline="#9aa7bd", width=int(6 * scale))
    return image


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    icon.save(PNG_PATH)
    icon.save(ICO_PATH, format="ICO", sizes=[(size, size) for size in ICO_SIZES])
    print(f"Wrote {PNG_PATH}")
    print(f"Wrote {ICO_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
