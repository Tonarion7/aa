"""장면별 영상을 ffmpeg로 만들고 하나로 이어 붙인다."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import captions as cap
from . import tts
from . import visuals as vis
from .episode import Episode


def _run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        tail = "\n".join(res.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg 실행 실패:\n{tail}")


def _scene_video(layout: Path, visual: Path, audio: Path, caps: list[tuple[Path, float, float]],
                 duration: float, zoom: bool, fps: int, out: Path) -> None:
    frames = max(1, round(duration * fps))
    step = 0.08 / frames  # 장면이 끝날 때 8% 확대되도록
    if zoom:
        vis_filter = (f"[1:v]zoompan=z='1+{step:.6f}*on':x='iw/2-(iw/zoom/2)':"
                      f"y='ih/2-(ih/zoom/2)':d=1:s={vis.VIS}x{vis.VIS}:fps={fps}[vis]")
    else:
        vis_filter = f"[1:v]scale={vis.VIS}:{vis.VIS},fps={fps}[vis]"
    parts = [vis_filter, f"[0:v][vis]overlay=0:{vis.VIS_Y}[b0]"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}", "-i", str(layout),
           "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}", "-i", str(visual),
           "-i", str(audio)]
    last = "b0"
    for i, (png, start, end) in enumerate(caps):
        cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}", "-i", str(png)]
        nxt = f"b{i + 1}"
        parts.append(f"[{last}][{i + 3}:v]overlay=0:{vis.CAP_Y}:"
                     f"enable='between(t,{start:.3f},{end:.3f})'[{nxt}]")
        last = nxt
    cmd += ["-filter_complex", ";".join(parts) + f";[{last}]format=yuv420p[v];[2:a]apad[a]",
            "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}",
            "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", str(out)]
    _run(cmd)


def make_episode(ep: Episode, cfg: dict, episode_path: Path, out_root: Path,
                 silent: bool = False) -> Path:
    work = out_root / ep.slug
    tmp = work / "work"
    tmp.mkdir(parents=True, exist_ok=True)
    voice = ep.voice or cfg["voice"]
    fps = int(cfg["fps"])

    layout = vis.render_layout(ep.hook, cfg, tmp / "layout.png")
    segments, credits = [], []
    total = 0.0
    for i, scene in enumerate(ep.scenes, 1):
        print(f"[{i}/{len(ep.scenes)}] {scene.visual['type']}: {scene.text[:24]}…")
        audio, words, dur = tts.synthesize(scene.text, voice, cfg["rate"], tmp / "tts",
                                           f"scene{i:02d}", silent=silent)
        duration = dur + float(cfg["scene_pause"])
        chunks = cap.split_chunks(scene.text)
        timed = cap.time_chunks(chunks, words, dur)
        cap_pngs = []
        for j, c in enumerate(timed, 1):
            png = vis.render_caption(c.text, cfg, tmp / f"cap{i:02d}_{j:02d}.png")
            end = duration if j == len(timed) else c.end
            cap_pngs.append((png, c.start, end))
        visual, vcredits = vis.render_visual(scene.visual, cfg, episode_path.parent,
                                             tmp / f"visual{i:02d}.png")
        credits += [c for c in vcredits if c not in credits]
        seg = tmp / f"scene{i:02d}.mp4"
        _scene_video(layout, visual, audio, cap_pngs, duration,
                     scene.visual.get("zoom_effect", True), fps, seg)
        segments.append(seg)
        total += duration

    concat_list = tmp / "concat.txt"
    concat_list.write_text("".join(f"file '{s.name}'\n" for s in segments), encoding="utf-8")
    joined = tmp / "joined.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(concat_list), "-c", "copy", str(joined)])

    final = work / f"{ep.slug}.mp4"
    bgm = (cfg.get("bgm") or {}).get("path")
    if bgm and Path(bgm).exists():
        vol = float(cfg["bgm"].get("volume", 0.12))
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined),
              "-stream_loop", "-1", "-i", bgm,
              "-filter_complex", f"[1:a]volume={vol}[bg];[0:a][bg]amix=inputs=2:duration=first:normalize=0[a]",
              "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(final)])
    else:
        shutil.copy(joined, final)

    _write_description(ep, credits, work / "description.txt")
    if total > 60:
        print(f"  [주의] 영상 길이가 {total:.1f}초입니다. 쇼츠는 짧을수록 유리해서 60초 이하를 권합니다.")
    return final


def _write_description(ep: Episode, credits: list[str], out: Path) -> None:
    lines = [ep.title, ""]
    if ep.sources:
        lines += ["참고 자료"] + [f"- {s}" for s in ep.sources] + [""]
    if credits:
        lines += ["이미지·지도 출처"] + [f"- {c}" for c in credits] + [""]
    if ep.hashtags:
        lines.append(" ".join(h if h.startswith("#") else f"#{h}" for h in ep.hashtags))
    out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
