"""사용법: python -m shorts episodes/001_gangnam.yaml [--silent]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ROOT, load_config
from .episode import EpisodeError, load_episode
from .render import make_episode


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 콘솔에서 한글이 깨지지 않게
    p = argparse.ArgumentParser(prog="python -m shorts", description="대본(YAML)으로 쇼츠 영상을 만듭니다.")
    p.add_argument("episode", type=Path, help="에피소드 대본 파일 (episodes/*.yaml)")
    p.add_argument("--silent", action="store_true",
                   help="AI 음성 없이 무음으로 빠르게 미리보기를 만듭니다 (인터넷 불필요)")
    p.add_argument("--config", type=Path, default=None, help="설정 파일 (기본: config.yaml)")
    p.add_argument("--out", type=Path, default=ROOT / "output", help="결과 폴더 (기본: output)")
    args = p.parse_args()

    try:
        cfg = load_config(args.config)
        ep = load_episode(args.episode)
    except (EpisodeError, FileNotFoundError) as e:
        print(f"오류: {e}")
        return 1

    final = make_episode(ep, cfg, args.episode.resolve(), args.out, silent=args.silent)
    print(f"\n완성: {final}")
    print(f"설명란 문구: {final.parent / 'description.txt'}")
    if ep.fact_check:
        print("\n업로드 전에 꼭 확인할 사실:")
        for item in ep.fact_check:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
