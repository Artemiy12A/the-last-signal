"""Contact sheets: labelled grids of key frames for review."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "IBMPlexMono-Light.ttf"


def contact_sheet(items: list[tuple[Image.Image, str]], out: Path, cols: int = 4, cell_w: int = 480,
                  title: str = "THE LAST SIGNAL  -  key frames") -> Path:
    if not items:
        raise ValueError("no frames")
    w0, h0 = items[0][0].size
    # crop the letterbox bars away so the sheet shows the picture
    active_h = int(round(w0 / 2.39))
    top = (h0 - active_h) // 2
    cell_h = int(round(cell_w * active_h / w0))
    pad, lab, head = 10, 22, 44
    rows = (len(items) + cols - 1) // cols
    W = cols * cell_w + (cols + 1) * pad
    H = head + rows * (cell_h + lab + pad) + pad
    sheet = Image.new("RGB", (W, H), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(FONT), 15)
    font_h = ImageFont.truetype(str(FONT), 20)
    d.text((pad, 12), title, fill=(220, 214, 204), font=font_h)
    for i, (img, label) in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad)
        y = head + r * (cell_h + lab + pad)
        pic = img.crop((0, top, w0, top + active_h)).resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        sheet.paste(pic, (x, y))
        d.text((x + 2, y + cell_h + 3), label, fill=(170, 165, 158), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=92)
    return out
