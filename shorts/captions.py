"""내레이션을 짧은 자막 조각으로 나누고, 조각마다 표시 시간을 정한다."""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHARS = {"ko": 16, "en": 26}  # 자막 한 조각의 최대 글자 수(공백·문장부호 제외)

_PUNCT = re.compile(r"[\s\.,!?…·'\"“”‘’()\[\]~\-:;]")


@dataclass
class Caption:
    text: str
    start: float
    end: float


def _plain_len(s: str) -> int:
    return len(_PUNCT.sub("", s))


def split_chunks(text: str, max_chars: int = MAX_CHARS["ko"]) -> list[str]:
    """문장 단위로 끊은 뒤, 긴 문장은 띄어쓰기 기준으로 max_chars 이하가 되게 나눈다."""
    sentences = [s.strip() for s in re.split(r"(?<=[\.!?…])\s+", text.strip()) if s.strip()]
    chunks: list[str] = []
    for sent in sentences:
        cur: list[str] = []
        for word in sent.split():
            trial = " ".join(cur + [word])
            if cur and _plain_len(trial) > max_chars:
                chunks.append(" ".join(cur))
                cur = [word]
            else:
                cur.append(word)
        if cur:
            chunks.append(" ".join(cur))
    # 자막 끝의 마침표는 지운다 (쇼츠 자막 관례)
    return [c.rstrip(".") for c in chunks]


def _time_at(char_index: int, words: list[dict]) -> float | None:
    """단어 시간 정보에서, 공백·문장부호를 뺀 n번째 글자가 읽히는 시각을 찾는다."""
    pos = 0
    for w in words:
        n = _plain_len(w["text"])
        if n == 0:
            continue
        if char_index < pos + n:
            frac = (char_index - pos) / n
            return w["start"] + frac * (w["end"] - w["start"])
        pos += n
    return None


def time_chunks(chunks: list[str], words: list[dict], duration: float) -> list[Caption]:
    """단어 시간 정보가 있으면 그것으로, 없으면 글자 수 비율로 자막 시간을 정한다."""
    lengths = [_plain_len(c) for c in chunks]
    total = sum(lengths) or 1
    starts: list[float] = []
    offset = 0
    for n in lengths:
        t = _time_at(offset, words) if words else None
        if t is None:
            t = duration * offset / total
        starts.append(t)
        offset += n
    starts[0] = 0.0
    caps = []
    for i, c in enumerate(chunks):
        end = starts[i + 1] if i + 1 < len(chunks) else duration
        caps.append(Caption(text=c, start=starts[i], end=max(end, starts[i] + 0.3)))
    return caps
