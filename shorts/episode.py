"""에피소드 대본(YAML)을 읽고 형식을 확인한다."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

VISUAL_TYPES = {"map", "image", "card", "video"}
LAYOUTS = {"explainer", "full"}


@dataclass
class Scene:
    text: str
    visual: dict
    voice: str | None = None   # 장면(대사)마다 다른 캐릭터 목소리
    rate: str | None = None
    pitch: str | None = None   # 예: "+30Hz" 높이면 아이 목소리 느낌


@dataclass
class Episode:
    slug: str
    title: str
    hook: list[str]
    scenes: list[Scene]
    sources: list[str] = field(default_factory=list)
    fact_check: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    voice: str | None = None
    layout: str = "explainer"


class EpisodeError(ValueError):
    pass


def load_episode(path: Path) -> Episode:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    for key in ("title", "hook", "scenes"):
        if key not in data:
            raise EpisodeError(f"'{key}' 항목이 없습니다: {path}")

    hook = data["hook"]
    if isinstance(hook, str):
        hook = [hook]
    if not 1 <= len(hook) <= 2:
        raise EpisodeError("hook(상단 제목)은 1~2줄로 적어 주세요.")

    scenes = []
    for i, raw in enumerate(data["scenes"], 1):
        text = (raw.get("text") or "").strip()
        visual = raw.get("visual") or {}
        if not text:
            raise EpisodeError(f"{i}번 장면에 text(내레이션)가 없습니다.")
        vtype = visual.get("type")
        if vtype not in VISUAL_TYPES:
            raise EpisodeError(
                f"{i}번 장면의 visual.type은 {sorted(VISUAL_TYPES)} 중 하나여야 합니다."
            )
        if vtype == "map" and "center" not in visual:
            raise EpisodeError(f"{i}번 장면 지도에 center: [위도, 경도]가 필요합니다.")
        if vtype == "video" and not visual.get("path"):
            raise EpisodeError(f"{i}번 장면 영상에 path가 필요합니다.")
        if vtype == "image" and not visual.get("path"):
            raise EpisodeError(f"{i}번 장면 이미지에 path가 필요합니다.")
        if vtype == "image" and not visual.get("credit"):
            raise EpisodeError(
                f"{i}번 장면 이미지에 credit(출처)이 필요합니다. 출처 없는 이미지는 쓰지 않습니다."
            )
        voice = raw.get("voice")
        if voice and voice in (data.get("characters") or {}):
            ch = data["characters"][voice]  # 캐릭터 이름으로 목소리 설정을 불러온다
            scenes.append(Scene(text=text, visual=visual, voice=ch.get("voice"),
                                rate=ch.get("rate"), pitch=ch.get("pitch")))
        else:
            scenes.append(Scene(text=text, visual=visual, voice=voice,
                                rate=raw.get("rate"), pitch=raw.get("pitch")))

    return Episode(
        slug=Path(path).stem,
        title=data["title"],
        hook=hook,
        scenes=scenes,
        sources=data.get("sources", []),
        fact_check=data.get("fact_check", []),
        hashtags=data.get("hashtags", []),
        voice=data.get("voice"),
        layout=_layout(data.get("layout", "explainer")),
    )


def _layout(value: str) -> str:
    if value not in LAYOUTS:
        raise EpisodeError(f"layout은 {sorted(LAYOUTS)} 중 하나여야 합니다.")
    return value
