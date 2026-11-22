"""설정 파일(config.yaml)을 읽고 기본값을 채운다."""
from __future__ import annotations

import os
import platform
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# 운영체제별로 기본 한글 굵은 글꼴 후보를 순서대로 찾는다.
FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",  # 윈도우: 맑은 고딕 Bold
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # 맥
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",  # 리눅스
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

DEFAULTS = {
    "font": "",
    "voice": "ko-KR-InJoonNeural",
    "rate": "+50%",
    "max_gap": 0.12,
    "fps": 30,
    "scene_pause": 0.05,
    "colors": {
        "background": "#0f1115",
        "title_band": "#000000",
        "title": "#ffffff",
        "title_accent": "#ffd400",
        "caption": "#ffffff",
        "caption_outline": "#000000",
        "map_line": "#ff3b30",
        "map_marker": "#ffd400",
    },
    "bgm": {"path": "", "volume": 0.12},
    "map": {
        "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "user_agent": "seoul-shorts-maker/0.1 (personal, low volume)",
        "attribution": "© OpenStreetMap contributors",
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def find_font(configured: str) -> str:
    if configured and os.path.exists(configured):
        return configured
    for cand in FONT_CANDIDATES:
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError(
        "한글 글꼴을 찾지 못했습니다. config.yaml의 font에 .ttf 경로를 적어 주세요. "
        f"(운영체제: {platform.system()})"
    )


def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "config.yaml"
    user = {}
    if path.exists():
        user = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = _merge(DEFAULTS, user)
    cfg["font"] = find_font(cfg.get("font", ""))
    return cfg
