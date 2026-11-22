"""에피소드 대본(YAML)을 읽고 형식을 확인한다."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

VISUAL_TYPES = {"map", "image", "card"}


@dataclass
class Scene:
    text: str
    visual: dict


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
        if vtype == "image" and not visual.get("path"):
            raise EpisodeError(f"{i}번 장면 이미지에 path가 필요합니다.")
        if vtype == "image" and not visual.get("credit"):
            raise EpisodeError(
                f"{i}번 장면 이미지에 credit(출처)이 필요합니다. 출처 없는 이미지는 쓰지 않습니다."
            )
        scenes.append(Scene(text=text, visual=visual))

    return Episode(
        slug=Path(path).stem,
        title=data["title"],
        hook=hook,
        scenes=scenes,
        sources=data.get("sources", []),
        fact_check=data.get("fact_check", []),
        hashtags=data.get("hashtags", []),
        voice=data.get("voice"),
    )
