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


def synthesize(text: str, voice: str, rate: str, out_dir: Path, name: str,
               silent: bool = False) -> tuple[Path, list[dict], float]:
    """음성 파일 경로, 단어 시간 목록, 길이(초)를 돌려준다. 같은 대본이면 다시 만들지 않는다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / f"{name}.json"
    audio = out_dir / (f"{name}.wav" if silent else f"{name}.mp3")
    key = {"text": text, "voice": voice, "rate": rate, "silent": silent}

    if audio.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("key") == key:
            return audio, meta["words"], meta["duration"]

    if silent:
        _silent(text, audio)
        words = []
    else:
        words = asyncio.run(_edge_tts(text, voice, rate, audio))
    duration = audio_duration(audio)
    meta_path.write_text(
        json.dumps({"key": key, "words": words, "duration": duration}, ensure_ascii=False),
        encoding="utf-8",
    )
    return audio, words, duration
