"""ffmpeg compose — セグメント結合 + BGM 合成 + -14 LUFS 正規化 + L3 再検証

Phase 1 ゲート (4/25) 条件 CINEMATIC_01 の「結合 + BGM + 公開用アップロード」
ステップで使用する共通パイプライン。cinematic-everyday-01 専用の combine.py
から呼び出される。

依存:
    ffmpeg / ffprobe (PATH)
    tools.renoise_validator (L3 検証)

外部 BGM (Uppbeat / YouTube Audio Library など商用利用可素材) は本モジュールでは
DL しません。権利確認のため呼び出し側で手動配置してください。
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys as _sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

# `python tools/ffmpeg_compose.py` 直接実行時に repo root が sys.path に無いと
# `from tools.renoise_validator import ...` が解決できないため先に足す。
# ライブラリとして import された場合 (__package__ あり) や `-m` 経由では何もしない。
if __name__ == "__main__" and __package__ in (None, ""):
    _REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(_REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_REPO_ROOT))

from tools.renoise_validator import (  # noqa: E402
    VideoSpec,
    validate_output_video,
)


class FfmpegNotAvailableError(RuntimeError):
    """ffmpeg / ffprobe が PATH に無い。`winget install ffmpeg` 等で導入が必要。"""


class ComposeError(RuntimeError):
    """結合・BGM 合成・LUFS 正規化の失敗。ffmpeg stderr を含む。"""


@dataclass(frozen=True)
class ComposeResult:
    final_path: Path
    duration_sec: float
    has_audio: bool
    final_lufs: Optional[float]
    spec_ok: bool


# ---------------------------------------------------------------------------
# 共通ユーティリティ
# ---------------------------------------------------------------------------
def _require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise FfmpegNotAvailableError(
                f"{tool} が PATH に見つかりません。ffmpeg をインストールしてください。"
            )


def _run(cmd: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        list(cmd),
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise ComposeError(
            f"ffmpeg コマンドが失敗しました (exit={proc.returncode}):\n"
            f"cmd = {shlex.join(str(a) for a in cmd)}\n"
            f"stderr =\n{proc.stderr}"
        )
    return proc


def _probe_duration(path: Path) -> float:
    _require_ffmpeg()
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    proc = _run(cmd)
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise ComposeError(f"duration 取得失敗: {path}") from exc


# ---------------------------------------------------------------------------
# concat manifest
# ---------------------------------------------------------------------------
def write_concat_manifest(
    segments: Sequence[Path],
    manifest_path: Path,
) -> Path:
    """ffmpeg concat demuxer 向けの manifest を書き出す (絶対パスで安全側)。"""
    lines = [f"file '{p.resolve().as_posix()}'" for p in segments]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


# ---------------------------------------------------------------------------
# concat (無音 mp4 中間生成)
# ---------------------------------------------------------------------------
def concat_segments(segments: Sequence[Path], out_path: Path) -> Path:
    """3 セグを無音 mp4 として結合。BGM 合成前の中間ファイル。"""
    _require_ffmpeg()
    missing = [str(s) for s in segments if not s.exists()]
    if missing:
        raise ComposeError(f"セグメントファイルが存在しません: {missing}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = write_concat_manifest(
        segments,
        out_path.with_suffix(".concat.txt"),
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest),
        "-c",
        "copy",
        "-an",  # concat 段階では音声を落とす (BGM は次ステップ)
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    _run(cmd)
    return out_path


# ---------------------------------------------------------------------------
# BGM 合成 + LUFS 正規化
# ---------------------------------------------------------------------------
def overlay_bgm(
    video_path: Path,
    bgm_path: Path,
    out_path: Path,
    *,
    target_lufs: float = -14.0,
    fade_sec: float = 0.5,
    duration_sec: Optional[float] = None,
) -> Path:
    """BGM を合成し -14 LUFS に正規化。前後 fade_sec 秒でフェードイン/アウト。

    `-shortest` で動画尺に合わせて音声をトリム。loudnorm は 1-pass 簡易版
    (公開前に 2-pass + print_format=json でより精密化することを推奨)。
    """
    _require_ffmpeg()
    if not bgm_path.exists():
        raise ComposeError(f"BGM ファイルが存在しません: {bgm_path}")

    if duration_sec is None:
        duration_sec = _probe_duration(video_path)
    fade_out_start = max(0.0, duration_sec - fade_sec)

    af = (
        f"afade=t=in:ss=0:d={fade_sec:.3f},"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade_sec:.3f},"
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(bgm_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-af",
        af,
        "-shortest",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    _run(cmd)
    return out_path


# ---------------------------------------------------------------------------
# LUFS 計測
# ---------------------------------------------------------------------------
_LUFS_INPUT_I_RE = re.compile(r"Input Integrated:\s*(-?\d+\.\d+)\s*LUFS", re.I)
_LUFS_OUTPUT_I_RE = re.compile(r"Output Integrated:\s*(-?\d+\.\d+)\s*LUFS", re.I)


def measure_lufs(path: Path) -> Optional[float]:
    """loudnorm を計測モードで流し、Integrated Loudness を読み取る。"""
    _require_ffmpeg()
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-af",
        "loudnorm=print_format=summary",
        "-f",
        "null",
        "-",
    ]
    proc = _run(cmd, check=False)

    # Output Integrated が出ていれば最終適用後の値、なければ Input Integrated
    out_match = _LUFS_OUTPUT_I_RE.search(proc.stderr)
    if out_match:
        try:
            return float(out_match.group(1))
        except ValueError:
            pass

    in_match = _LUFS_INPUT_I_RE.search(proc.stderr)
    if in_match:
        try:
            return float(in_match.group(1))
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# エンド to エンド
# ---------------------------------------------------------------------------
def finalize_cinematic(
    segments: Sequence[Path],
    out_path: Path,
    *,
    bgm_path: Optional[Path] = None,
    expected: Optional[VideoSpec] = None,
    target_lufs: float = -14.0,
    fade_sec: float = 0.5,
    skip_l3: bool = False,
) -> ComposeResult:
    """結合 → (BGM 合成) → L3 再検証 → LUFS 計測 の一気通貫パイプライン。

    skip_l3=True の場合 L3 再検証をスキップ (mediapipe 未導入の CI 等で使用)。
    """
    _require_ffmpeg()

    silent_path = out_path.with_name(out_path.stem + "_silent.mp4")
    concat_segments(segments, silent_path)

    if bgm_path is None:
        final_path = out_path
        if silent_path.resolve() != final_path.resolve():
            shutil.copyfile(silent_path, final_path)
    else:
        final_path = overlay_bgm(
            silent_path,
            bgm_path,
            out_path,
            target_lufs=target_lufs,
            fade_sec=fade_sec,
        )

    spec_ok = False
    if expected is not None and not skip_l3:
        # BGM を入れた場合は音声トラック OK にして allow_audio=True を強制
        adjusted = VideoSpec(
            duration_sec=expected.duration_sec,
            width=expected.width,
            height=expected.height,
            tolerance_sec=expected.tolerance_sec,
            allow_audio=bool(bgm_path is not None),
        )
        validate_output_video(final_path, expected=adjusted)
        spec_ok = True

    lufs = measure_lufs(final_path) if bgm_path is not None else None
    return ComposeResult(
        final_path=final_path,
        duration_sec=_probe_duration(final_path),
        has_audio=(bgm_path is not None),
        final_lufs=lufs,
        spec_ok=spec_ok,
    )


# ---------------------------------------------------------------------------
# Self-check (smoke)
# ---------------------------------------------------------------------------
def _smoke_test() -> int:
    """実 mp4 が無くても import と設定確認だけできる smoke。"""
    try:
        _require_ffmpeg()
        print("[OK] ffmpeg / ffprobe は PATH に存在します。")
    except FfmpegNotAvailableError as exc:
        print(f"[WARN] {exc}")
    print(
        "[INFO] 本モジュールの動作確認には実 mp4 (各 10s / 1080x1920 / 9:16) が必要です。"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_smoke_test())
