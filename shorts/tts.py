"""내레이션을 AI 음성(edge-tts)으로 만들고, 단어별 시간 정보를 함께 저장한다."""
from __future__ import annotations

import asyncio
import json
import math
import subprocess
import wave
from pathlib import Path


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


async def _edge_tts(text: str, voice: str, rate: str, mp3: Path) -> list[dict]:
    import edge_tts

    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset/duration 단위는 100나노초
                words.append({
                    "start": chunk["offset"] / 1e7,
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                    "text": chunk["text"],
                })
    return words


def _silent(text: str, wav: Path) -> None:
    """음성 없이 미리보기용 무음 파일을 만든다 (한 글자당 약 0.13초)."""
    seconds = max(1.5, len(text.replace(" ", "")) * 0.13)
    rate = 24000
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * math.ceil(seconds * rate))


def keep_intervals(words: list[dict], duration: float, max_gap: float, lead: float = 0.04,
                   tail: float = 0.08) -> list[tuple[float, float]]:
    """단어 사이 공백이 max_gap보다 길면 그만큼 잘라 낸, 남길 구간 목록을 만든다."""
    if not words:
        return [(0.0, duration)]
    keep = [[max(0.0, words[0]["start"] - lead), None]]
    for cur, nxt in zip(words, words[1:]):
        gap = nxt["start"] - cur["end"]
        if gap > max_gap:
            keep[-1][1] = cur["end"] + max_gap / 2
            keep.append([nxt["start"] - max_gap / 2, None])
    keep[-1][1] = min(duration, words[-1]["end"] + tail)
    return [(a, b) for a, b in keep if b > a]


def remap(t: float, keep: list[tuple[float, float]]) -> float:
    """원래 음성의 시각 t를 공백을 잘라 낸 뒤의 시각으로 바꾼다."""
    out = 0.0
    for a, b in keep:
        if t <= a:
            return out
        if t <= b:
            return out + (t - a)
        out += b - a
    return out


def tighten(src: Path, dst: Path, words: list[dict], max_gap: float) -> list[dict]:
    """대사 사이 긴 공백을 잘라 내고, 단어 시간도 거기에 맞춰 옮긴다."""
    keep = keep_intervals(words, audio_duration(src), max_gap)
    parts = [f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[p{i}]" for i, (a, b) in enumerate(keep)]
    joined = "".join(f"[p{i}]" for i in range(len(keep)))
    filt = ";".join(parts) + f";{joined}concat=n={len(keep)}:v=0:a=1[a]"
    res = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                          "-filter_complex", filt, "-map", "[a]", str(dst)],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"공백 자르기 실패: {res.stderr[-500:]}")
    return [{**w, "start": remap(w["start"], keep), "end": remap(w["end"], keep)} for w in words]


def synthesize(text: str, voice: str, rate: str, out_dir: Path, name: str,
               silent: bool = False, max_gap: float | None = None) -> tuple[Path, list[dict], float]:
    """음성 파일 경로, 단어 시간 목록, 길이(초)를 돌려준다. 같은 대본이면 다시 만들지 않는다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / f"{name}.json"
    audio = out_dir / (f"{name}.wav" if silent else f"{name}.mp3")
    key = {"text": text, "voice": voice, "rate": rate, "silent": silent, "max_gap": max_gap}

    if audio.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("key") == key:
            return audio, meta["words"], meta["duration"]

    if silent:
        _silent(text, audio)
        words = []
    else:
        raw = out_dir / f"{name}_raw.mp3"
        words = asyncio.run(_edge_tts(text, voice, rate, raw))
        if max_gap and words:
            words = tighten(raw, audio, words, max_gap)
        else:
            raw.replace(audio)
    duration = audio_duration(audio)
    meta_path.write_text(
        json.dumps({"key": key, "words": words, "duration": duration}, ensure_ascii=False),
        encoding="utf-8",
    )
    return audio, words, duration
