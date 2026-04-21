"""cinematic-everyday-01 結合 + BGM + LUFS 最終化スクリプト

Phase 1 ゲート (4/25) 条件 CINEMATIC_01 の「ffmpeg 結合 + BGM 合成」ステップ。
3 セグメント (S1/S2/S3) の生成と L3 検証が完了した後、本スクリプトを実行する。

使い方:
    # 無音版 (BGM は後で追加する場合)
    python combine.py

    # BGM 付き (Uppbeat / YouTube Audio Library から事前 DL)
    python combine.py --bgm ../bgm/uppbeat_cinematic_everyday.mp3

    # 出力先を指定
    python combine.py --out videos/cinematic-everyday-01_final.mp4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# リポジトリルートを sys.path に注入 (tools.* を import するため)
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]  # cinematic-everyday-01 → 企画 → SNS動画運用事業部 → ArcoCapital → repo root
sys.path.insert(0, str(REPO_ROOT))

from tools.ffmpeg_compose import (  # noqa: E402
    ComposeError,
    FfmpegNotAvailableError,
    finalize_cinematic,
)
from tools.renoise_validator import (  # noqa: E402
    ValidatorBackendUnavailableError,
    VideoSpec,
)


VIDEOS_DIR = HERE / "videos"
SEGMENTS = [VIDEOS_DIR / f"{name}.mp4" for name in ("S1", "S2", "S3")]
EXPECTED = VideoSpec(
    duration_sec=30.0,
    width=1080,
    height=1920,
    tolerance_sec=0.5,
    allow_audio=False,  # BGM 合成時は finalize_cinematic が上書きする
)


def _check_segments() -> list[str]:
    return [p.name for p in SEGMENTS if not p.exists()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="cinematic-everyday-01 の最終結合スクリプト",
    )
    parser.add_argument(
        "--bgm",
        type=Path,
        default=None,
        help="BGM ファイル (mp3/wav)。未指定なら無音 mp4 を出力",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=VIDEOS_DIR / "cinematic-everyday-01_final.mp4",
        help="最終 mp4 の出力先",
    )
    parser.add_argument(
        "--target-lufs",
        type=float,
        default=-14.0,
        help="Instagram Reels 推奨の -14 LUFS (変更非推奨)",
    )
    parser.add_argument(
        "--skip-l3",
        action="store_true",
        help="mediapipe 未導入環境で L3 再検証をスキップ (本番公開前には必ず外すこと)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイル存在チェックと設定表示のみ実行 (ffmpeg は起動しない)",
    )
    args = parser.parse_args()

    missing = _check_segments()

    if args.dry_run:
        # dry-run は「config 表示のみ」。セグメント未生成でも落とさず、警告だけ返す。
        print(json.dumps(
            {
                "segments": [str(p) for p in SEGMENTS],
                "segments_exist": not missing,
                "missing_segments": missing,
                "out": str(args.out),
                "bgm": str(args.bgm) if args.bgm else None,
                "target_lufs": args.target_lufs,
                "expected": {
                    "duration_sec": EXPECTED.duration_sec,
                    "width": EXPECTED.width,
                    "height": EXPECTED.height,
                    "tolerance_sec": EXPECTED.tolerance_sec,
                },
                "note": "dry-run モード: ffmpeg は起動していません。",
            },
            ensure_ascii=False,
            indent=2,
        ))
        if missing:
            print(
                f"[WARN] dry-run: 未生成セグメントあり {missing} — 本実行前に生成してください。",
                file=sys.stderr,
            )
        return 0

    if missing:
        print(
            f"[ERROR] 未生成セグメントあり: {missing}\n"
            f"        先に shots/RUN.md の手順 1 or 2 で Renoise 生成 + L3 検証を済ませてください。\n"
            f"        videos/ に S1.mp4 / S2.mp4 / S3.mp4 を配置した後、再実行。",
            file=sys.stderr,
        )
        return 1

    try:
        result = finalize_cinematic(
            SEGMENTS,
            args.out,
            bgm_path=args.bgm,
            expected=EXPECTED,
            target_lufs=args.target_lufs,
            skip_l3=args.skip_l3,
        )
    except FfmpegNotAvailableError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except ValidatorBackendUnavailableError as exc:
        print(
            f"[ERROR] L3 検証バックエンド不在: {exc}\n"
            f"        `pip install mediapipe opencv-python` で導入するか、"
            f"--skip-l3 を指定して手動検証に切り替えてください。",
            file=sys.stderr,
        )
        return 3
    except ComposeError as exc:
        print(f"[ERROR] compose 失敗:\n{exc}", file=sys.stderr)
        return 4

    summary = {
        "final_path": str(result.final_path),
        "duration_sec": round(result.duration_sec, 2),
        "has_audio": result.has_audio,
        "final_lufs": result.final_lufs,
        "spec_ok": result.spec_ok,
        "target_lufs": args.target_lufs,
        "expected": {
            "duration_sec": EXPECTED.duration_sec,
            "resolution": f"{EXPECTED.width}x{EXPECTED.height}",
            "tolerance_sec": EXPECTED.tolerance_sec,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if result.has_audio and result.final_lufs is not None:
        drift = abs(result.final_lufs - args.target_lufs)
        if drift > 1.5:
            print(
                f"[WARN] 最終 LUFS {result.final_lufs:.1f} が目標 {args.target_lufs} から "
                f"{drift:.1f} dB 乖離しています。2-pass loudnorm での再調整を推奨。",
                file=sys.stderr,
            )
    elif not result.has_audio:
        print(
            "[INFO] 無音 mp4 を出力しました。BGM 追加時は --bgm を指定して再実行。",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
