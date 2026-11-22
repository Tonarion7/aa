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


FULL_CAP_Y = 1250  # 전체 화면 모드에서 자막 위치


def _scene_video(layout: Path, visual: Path, is_video: bool, full: bool, audio: Path,
                 caps: list[tuple[Path, float, float]], credit: Path | None, duration: float,
                 zoom: bool, clip_volume: float, fps: int, out: Path, clip_start: float = 0.0) -> None:
    """한 장면을 영상으로 만든다.
    full=False: 위 제목 틀 + 가운데 정사각형 그림(지도, 카드, 사진, 영상) + 아래 자막
    full=True : 영상(또는 그림)이 화면 전체, 그 위에 제목과 자막
    """
    t = f"{duration:.3f}"
    still = ["-loop", "1", "-framerate", str(fps), "-t", t]
    seek = ["-ss", f"{clip_start:.3f}"] if clip_start > 0 else []
    vis_in = (seek + ["-stream_loop", "-1", "-t", t, "-i", str(visual)] if is_video
              else still + ["-i", str(visual)])
    w, h = (vis.W, vis.H) if full else (vis.VIS, vis.VIS)
    frames = max(1, round(duration * fps))
    if zoom and not is_video:
        step = 0.08 / frames  # 장면이 끝날 때 8% 확대되도록
        src = f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
        vis_filter = (f"[1:v]{src}zoompan=z='1+{step:.6f}*on':x='iw/2-(iw/zoom/2)':"
                      f"y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}[vis]")
    else:
        vis_filter = (f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                      f"crop={w}:{h},fps={fps},setsar=1[vis]")

    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + still + ["-i", str(layout)] + vis_in + ["-i", str(audio)]
    if full:
        # 영상이 바닥, 제목 그림(투명 배경)을 그 위에
        parts = [vis_filter, "[vis][0:v]overlay=0:0[b0]"]
        cap_y, credit_y = FULL_CAP_Y, vis.H - vis.CREDIT_H
    else:
        parts = [vis_filter, f"[0:v][vis]overlay=0:{vis.VIS_Y}[b0]"]
        cap_y, credit_y = vis.CAP_Y, vis.VIS_Y + vis.VIS - vis.CREDIT_H

    overlays = [(p, cap_y, s, e) for p, s, e in caps]
    if credit:
        overlays.append((credit, credit_y, 0.0, duration))
    last = "b0"
    for i, (png, y, start, end) in enumerate(overlays):
        cmd += still + ["-i", str(png)]
        nxt = f"b{i + 1}"
        parts.append(f"[{last}][{i + 3}:v]overlay=0:{y}:"
                     f"enable='between(t,{start:.3f},{end:.3f})'[{nxt}]")
        last = nxt

    parts.append(f"[{last}]format=yuv420p[v]")
    if is_video and clip_volume > 0:
        # AI 영상에 들어 있는 효과음·배경 소리를 작게 섞는다 (소리가 없는 영상이면 무시됨)
        parts.append(f"[1:a]volume={clip_volume}[ca];[2:a]apad[va];"
                     f"[va][ca]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        parts.append("[2:a]apad[a]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]", "-t", t,
            "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", str(out)]
    _run(cmd)


def _has_audio(path: Path) -> bool:
    res = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                          "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True)
    return bool(res.stdout.strip())


def make_episode(ep: Episode, cfg: dict, episode_path: Path, out_root: Path,
                 silent: bool = False) -> Path:
    work = out_root / ep.slug
    tmp = work / "work"
    tmp.mkdir(parents=True, exist_ok=True)
    voice = ep.voice or cfg["voice"]
    fps = int(cfg["fps"])

    full = ep.layout == "full"
    layout = (vis.render_layout_full(ep.hook, cfg, tmp / "layout.png") if full
              else vis.render_layout(ep.hook, cfg, tmp / "layout.png"))
    segments, credits = [], []
    total = 0.0
    for i, scene in enumerate(ep.scenes, 1):
        print(f"[{i}/{len(ep.scenes)}] {scene.visual['type']}: {scene.text[:24]}…")
        audio, words, dur = tts.synthesize(scene.text, scene.voice or voice,
                                           scene.rate or cfg["rate"], tmp / "tts",
                                           f"scene{i:02d}", silent=silent,
                                           max_gap=cfg.get("max_gap"), pitch=scene.pitch)
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
        credit_png = vis.render_credit(vcredits, cfg, tmp / f"credit{i:02d}.png") if vcredits else None
        seg = tmp / f"scene{i:02d}.mp4"
        is_video = scene.visual["type"] == "video"
        clip_vol = float(scene.visual.get("clip_volume", 0.3)) if is_video else 0.0
        if is_video and not _has_audio(visual):
            clip_vol = 0.0
        _scene_video(layout, visual, is_video, full, audio, cap_pngs, credit_png, duration,
                     scene.visual.get("zoom_effect", True), clip_vol, fps, seg,
                     clip_start=float(scene.visual.get("start", 0)) if is_video else 0.0)
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
