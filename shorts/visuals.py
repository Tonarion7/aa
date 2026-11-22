"""화면 그림을 만든다: 상단 제목 틀, 장면별 지도·이미지·카드, 자막 이미지."""
from __future__ import annotations

import io
import math
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from .config import ROOT

W, H = 1080, 1920
VIS_Y = 420           # 장면 그림이 놓이는 세로 위치
VIS = 1080            # 장면 그림 크기(정사각형)
SCALE = 2             # 확대 효과를 부드럽게 하려고 2배 크기로 그린다
CAP_Y = 1540          # 자막이 놓이는 세로 위치
CAP_H = 300


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _fit_size(draw, text, path, start, max_w, min_size=40):
    size = start
    while size > min_size:
        f = font(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return font(path, min_size)


def _wrap(draw, text, f, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and draw.textlength(trial, font=f) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


# ---------- 상단 제목 틀 ----------

def render_layout(hook: list[str], cfg: dict, out: Path) -> Path:
    c = cfg["colors"]
    img = Image.new("RGB", (W, H), c["background"])
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, VIS_Y - 20], fill=c["title_band"])
    colors = [c["title"], c["title_accent"]] if len(hook) == 2 else [c["title_accent"]]
    fonts = [_fit_size(d, line, cfg["font"], 96, W - 80) for line in hook]
    heights = [f.getbbox("가")[3] for f in fonts]
    gap = 24
    y = (VIS_Y - 20 - (sum(heights) + gap * (len(hook) - 1))) // 2
    for line, f, col, h in zip(hook, fonts, colors, heights):
        d.text((W // 2, y), line, font=f, fill=col, anchor="mt")
        y += h + gap
    img.save(out)
    return out


def render_layout_full(hook: list[str], cfg: dict, out: Path) -> Path:
    """전체 화면 모드: 투명 배경 위 맨 위에 제목만 얹는다."""
    c = cfg["colors"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    colors = [c["title"], c["title_accent"]] if len(hook) == 2 else [c["title_accent"]]
    y = 150
    for line, col in zip(hook, colors):
        f = _fit_size(d, line, cfg["font"], 84, W - 80)
        d.text((W // 2, y), line, font=f, fill=col, anchor="mt",
               stroke_width=8, stroke_fill="#000000")
        y += f.getbbox("가")[3] + 24
    img.save(out)
    return out


# ---------- 자막 ----------

def render_caption(text: str, cfg: dict, out: Path) -> Path:
    c = cfg["colors"]
    img = Image.new("RGBA", (W, CAP_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(cfg["font"], 76)
    lines = _wrap(d, text, f, W - 120)
    if len(lines) == 2:
        # 두 줄이면 줄 길이를 비슷하게 맞춘다 (둘째 줄에 한 단어만 남지 않게)
        words = text.split()
        best = min(range(1, len(words)),
                   key=lambda k: max(d.textlength(" ".join(words[:k]), font=f),
                                     d.textlength(" ".join(words[k:]), font=f)))
        cand = [" ".join(words[:best]), " ".join(words[best:])]
        if all(d.textlength(x, font=f) <= W - 120 for x in cand):
            lines = cand
    lh = 96
    y = (CAP_H - lh * len(lines)) // 2
    for line in lines:
        d.text((W // 2, y), line, font=f, fill=c["caption"], anchor="mt",
               stroke_width=8, stroke_fill=c["caption_outline"])
        y += lh
    img.save(out)
    return out


# ---------- 출처 표기 ----------
# 확대 효과 때문에 그림 안에 넣으면 출처가 화면 밖으로 밀리므로, 확대와 상관없이 고정된 위치에 따로 얹는다.
CREDIT_H = 44


def render_credit(texts: list[str], cfg: dict, out: Path) -> Path:
    text = " · ".join(texts)
    img = Image.new("RGBA", (W, CREDIT_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(cfg["font"], 24)
    tw = d.textlength(text, font=f)
    d.rectangle([W - tw - 28, 0, W, CREDIT_H], fill=(0, 0, 0, 170))
    d.text((W - 14, CREDIT_H // 2), text, font=f, fill="#ffffff", anchor="rm")
    img.save(out)
    return out


# ---------- 지도 ----------

def _project(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 256 * 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n
    return x, y


def _tile(z: int, x: int, y: int, cfg: dict) -> Image.Image:
    cache = ROOT / "cache" / "tiles" / str(z) / str(x)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{y}.png"
    if not path.exists():
        url = cfg["map"]["tile_url"].format(z=z, x=x, y=y)
        r = requests.get(url, headers={"User-Agent": cfg["map"]["user_agent"]}, timeout=15)
        r.raise_for_status()
        path.write_bytes(r.content)
        time.sleep(0.05)  # 지도 서버에 부담을 주지 않도록 천천히 받는다
    return Image.open(io.BytesIO(path.read_bytes())).convert("RGB")


def _base_map(center, z, size, cfg) -> tuple[Image.Image, bool]:
    cx, cy = _project(center[0], center[1], z)
    x0, y0 = cx - size / 2, cy - size / 2
    img = Image.new("RGB", (size, size), "#dfe3e8")
    try:
        for tx in range(int(x0 // 256), int((x0 + size) // 256) + 1):
            for ty in range(int(y0 // 256), int((y0 + size) // 256) + 1):
                img.paste(_tile(z, tx, ty, cfg), (int(tx * 256 - x0), int(ty * 256 - y0)))
        return img, True
    except Exception as e:  # 인터넷이 안 되거나 지도 서버가 막으면 단순한 배경으로 대신한다
        print(f"  [경고] 지도 타일을 받지 못해 단순 배경으로 그립니다: {e}")
        img = Image.new("RGB", (size, size), "#1b2430")
        d = ImageDraw.Draw(img)
        for i in range(0, size, 120):
            d.line([(i, 0), (i, size)], fill="#243042", width=2)
            d.line([(0, i), (size, i)], fill="#243042", width=2)
        return img, False


def render_map(v: dict, cfg: dict, out: Path) -> tuple[Path, list[str]]:
    size = VIS * SCALE
    z = int(v.get("zoom", 12)) + 1  # 2배 크기로 그리므로 한 단계 더 확대한 타일을 쓴다
    center = v["center"]
    img, ok = _base_map(center, z, size, cfg)
    d = ImageDraw.Draw(img)
    cx, cy = _project(center[0], center[1], z)

    def px(lat, lon):
        x, y = _project(lat, lon, z)
        return x - cx + size / 2, y - cy + size / 2

    c = cfg["colors"]
    for line in v.get("lines", []):
        pts = [px(lat, lon) for lat, lon in line.get("points", [])]
        if len(pts) >= 2:
            d.line(pts, fill=line.get("color", c["map_line"]), width=28, joint="curve")
    for area in v.get("areas", []):
        pts = [px(lat, lon) for lat, lon in area.get("points", [])]
        if len(pts) >= 3:
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(overlay).polygon(pts, fill=(255, 59, 48, 90), outline=(255, 59, 48, 255))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)

    label_font = font(cfg["font"], 100)
    for m in v.get("markers", []):
        x, y = px(m["lat"], m["lon"])
        r = 36
        d.ellipse([x - r, y - r, x + r, y + r], fill=c["map_marker"], outline="#000000", width=6)
        if m.get("label"):
            tw = d.textlength(m["label"], font=label_font)
            bx, by = x - tw / 2 - 36, y - r - 170
            d.rounded_rectangle([bx, by, bx + tw + 72, by + 140], radius=32, fill="#000000")
            d.text((x, by + 70), m["label"], font=label_font, fill="#ffffff", anchor="mm")

    credits = []
    if ok:
        att = cfg["map"]["attribution"]
        credits.append(att)
    img.save(out)
    return out, credits


# ---------- 이미지 ----------

def render_image(v: dict, cfg: dict, base_dir: Path, out: Path) -> tuple[Path, list[str]]:
    size = VIS * SCALE
    src = Path(v["path"])
    if not src.is_absolute():
        src = (base_dir / src) if (base_dir / src).exists() else ROOT / src
    img = Image.open(src).convert("RGB")
    # 정사각형을 꽉 채우도록 잘라 낸다
    scale = max(size / img.width, size / img.height)
    img = img.resize((math.ceil(img.width * scale), math.ceil(img.height * scale)), Image.LANCZOS)
    left, upper = (img.width - size) // 2, (img.height - size) // 2
    img = img.crop((left, upper, left + size, upper + size))
    img.save(out)
    return out, [v["credit"]]


# ---------- 카드 (연도, 숫자, 핵심 문장) ----------

def render_card(v: dict, cfg: dict, out: Path) -> tuple[Path, list[str]]:
    size = VIS * SCALE
    c = cfg["colors"]
    img = Image.new("RGB", (size, size), "#161b22")
    d = ImageDraw.Draw(img)
    heading = str(v.get("heading", ""))
    body = str(v.get("body", ""))
    hf = _fit_size(d, heading, cfg["font"], 360, size - 240, 120)
    bf = font(cfg["font"], 110)
    body_lines = _wrap(d, body, bf, size - 280) if body else []
    total = (hf.getbbox("가")[3] if heading else 0) + 80 + 150 * len(body_lines)
    y = (size - total) // 2
    if heading:
        d.text((size // 2, y), heading, font=hf, fill=c["title_accent"], anchor="mt")
        y += hf.getbbox("가")[3] + 80
    for line in body_lines:
        d.text((size // 2, y), line, font=bf, fill="#ffffff", anchor="mt")
        y += 150
    img.save(out)
    return out, []


def resolve_path(p: str, base_dir: Path) -> Path:
    src = Path(p)
    if src.is_absolute():
        return src
    return (base_dir / src) if (base_dir / src).exists() else ROOT / src


def render_visual(v: dict, cfg: dict, base_dir: Path, out: Path) -> tuple[Path, list[str]]:
    kind = v["type"]
    if kind == "video":
        # 영상은 그대로 쓰고, 출처가 있으면 표기한다 (AI로 만든 영상이면 생략 가능)
        return resolve_path(v["path"], base_dir), ([v["credit"]] if v.get("credit") else [])
    if kind == "map":
        return render_map(v, cfg, out)
    if kind == "image":
        return render_image(v, cfg, base_dir, out)
    return render_card(v, cfg, out)
