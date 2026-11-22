"""내레이션을 짧은 자막 조각으로 나누고, 조각마다 표시 시간을 정한다."""
from __future__ import annotations

import math
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


def _balanced(words: list[str], n: int) -> list[str]:
    """단어들을 순서대로 n덩어리로 나누되, 가장 긴 덩어리가 최대한 짧아지게 한다."""
    w = len(words)
    lens = [_plain_len(x) for x in words]
    pre = [0]
    for L in lens:
        pre.append(pre[-1] + L)
    INF = float("inf")
    best = [[INF] * (w + 1) for _ in range(n + 1)]
    cut = [[0] * (w + 1) for _ in range(n + 1)]
    best[0][0] = 0
    for k in range(1, n + 1):
        for j in range(k, w + 1):
            for i in range(k - 1, j):
                cost = max(best[k - 1][i], pre[j] - pre[i])
                if cost < best[k][j]:
                    best[k][j], cut[k][j] = cost, i
    out, j = [], w
    for k in range(n, 0, -1):
        i = cut[k][j]
        out.append(" ".join(words[i:j]))
        j = i
    return out[::-1]


def split_chunks(text: str, max_chars: int = MAX_CHARS["ko"]) -> list[str]:
    """문장 단위로 끊은 뒤, 긴 문장은 비슷한 길이의 덩어리로 나눈다 (한 단어만 남는 덩어리 방지)."""
    sentences = [s.strip() for s in re.split(r"(?<=[\.!?…])\s+(?=[A-Z가-힣0-9\"'“‘])", text.strip())
                 if s.strip()]
    chunks: list[str] = []
    for sent in sentences:
        words = sent.split()
        n = max(1, math.ceil(_plain_len(sent) / max_chars))
        n = min(n, len(words))
        chunks += _balanced(words, n)
    return [_strip_period(c) for c in chunks]


def _strip_period(c: str) -> str:
    """자막 끝의 마침표 하나는 지운다 (쇼츠 자막 관례). 'a.m.' 같은 약어와 '...'은 그대로 둔다."""
    if c.endswith("...") or re.search(r"\b\w\.\w\.$", c):
        return c
    return c[:-1] if c.endswith(".") else c


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
