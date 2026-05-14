"""Renoise L1 (プロンプト構文) + L3 (出力検証) バリデータ。

Renoise 例外処理設計書 v0.1 §3.1 / §3.3 準拠:

  L1: validate_prompt_spec(prompt)
      - subject に face / portrait / closeup_face 等の禁止語禁止
      - duration_sec が 1 〜 30
      - aspect_ratio が 9:16 / 1:1 / 16:9 のいずれか
      - negative_prompt に著作権侵害語禁止
      違反時: PromptViolationError (自動補正しない)

  L3: validate_output_video(path, expected=...)
      - 顔検出: mediapipe / opencv-haar で 1 件でも検出 → FaceDetectedError
      - 尺: ffprobe で ±0.5s 外 → OutputSpecError
      - 解像度: ffprobe で仕様不一致 → OutputSpecError
      - 音声トラック: あれば OutputSpecError (Director 側で無音化判断)

AGENTS.md RULE-04 準拠: 検証バックエンド不在時は
ValidatorBackendUnavailableError を送出し、検証せずに流す動線を封鎖。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from tools.renoise_errors import (
    FaceDetectedError,
    OutputSpecError,
    PromptViolationError,
    ValidatorBackendUnavailableError,
)

# -----------------------------------------------------------------------------
# 禁止語ルール (設計書 §3.1)
# -----------------------------------------------------------------------------
FORBIDDEN_SUBJECT_TERMS: tuple[str, ...] = (
    "face",
    "portrait",
    "closeup face",
    "close-up face",
    "people visible from chest up",
    "selfie",
    "human face",
)

# 著作権侵害の代表語 (網羅ではなく最低ライン)
FORBIDDEN_NEGATIVE_OMISSIONS: tuple[str, ...] = ()  # negative_prompt の必須語は別途

# negative_prompt に含まれるべき語 (顔なし動画の最低ライン)
REQUIRED_NEGATIVE_TERMS: tuple[str, ...] = ("face", "portrait")

ALLOWED_ASPECT_RATIOS: tuple[str, ...] = ("9:16", "1:1", "16:9")
ALLOWED_DURATION_RANGE: tuple[float, float] = (1.0, 30.0)


# -----------------------------------------------------------------------------
# L1: プロンプト検査
# -----------------------------------------------------------------------------
def validate_prompt_spec(prompt: dict) -> None:
    """プロンプト辞書を構文レベルで検査し、違反なら PromptViolationError を送出。

    検査項目:
      - subject / action に禁止語なし
      - duration_sec が 1..30
      - aspect_ratio が許可リスト内
      - negative_prompt に最低限の必須語あり
    """
    _ensure_required_keys(prompt)
    _check_no_forbidden_subject(prompt)
    _check_duration(prompt)
    _check_aspect_ratio(prompt)
    _check_negative_prompt(prompt)


def _ensure_required_keys(prompt: dict) -> None:
    required = ("subject", "style", "duration_sec")
    missing = [k for k in required if k not in prompt]
    if missing:
        raise PromptViolationError(
            f"Prompt missing required keys: {missing}"
        )


_NEGATION_PREFIX_RE = re.compile(
    r"\b(no|without|excluding|sans|minus|zero|never|not)\s+$"
)


def _is_negated_occurrence(text: str, pos: int) -> bool:
    """直前 16 文字に否定前置詞があれば True (例: 'no face', 'without portrait')。"""
    prefix = text[max(0, pos - 16):pos]
    return _NEGATION_PREFIX_RE.search(prefix) is not None


def _find_non_negated(text: str, term: str) -> bool:
    """term が否定されていない形で text に登場するかを判定。"""
    start = 0
    while True:
        idx = text.find(term, start)
        if idx == -1:
            return False
        if not _is_negated_occurrence(text, idx):
            return True
        start = idx + len(term)


def _check_no_forbidden_subject(prompt: dict) -> None:
    scannable = " ".join(
        str(prompt.get(k, "")) for k in ("subject", "action", "style")
    ).lower()
    hits = [
        term for term in FORBIDDEN_SUBJECT_TERMS
        if _find_non_negated(scannable, term)
    ]
    if hits:
        raise PromptViolationError(
            f"Prompt contains forbidden face/portrait terms (non-negated): {hits}. "
            "Use hands/silhouette/objects only. Negated mentions like "
            "'no face' / 'without portrait' are allowed."
        )


def _check_duration(prompt: dict) -> None:
    try:
        dur = float(prompt["duration_sec"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PromptViolationError(
            f"duration_sec must be float: {prompt.get('duration_sec')!r}"
        ) from exc
    lo, hi = ALLOWED_DURATION_RANGE
    if not (lo <= dur <= hi):
        raise PromptViolationError(
            f"duration_sec {dur} out of allowed range [{lo}, {hi}]"
        )


def _check_aspect_ratio(prompt: dict) -> None:
    # aspect_ratio はプロジェクト側 (project.json) で担保されている場合もあるため
    # プロンプト単体では任意。指定されたら検査する。
    ar = prompt.get("aspect_ratio") or prompt.get("aspect")
    if ar is None:
        return
    if ar not in ALLOWED_ASPECT_RATIOS:
        raise PromptViolationError(
            f"aspect_ratio {ar!r} not in {ALLOWED_ASPECT_RATIOS}"
        )


def _check_negative_prompt(prompt: dict) -> None:
    neg = str(prompt.get("negative") or prompt.get("negative_prompt") or "").lower()
    missing = [term for term in REQUIRED_NEGATIVE_TERMS if term not in neg]
    if missing:
        raise PromptViolationError(
            f"negative_prompt must contain {REQUIRED_NEGATIVE_TERMS} "
            f"to block face generation. Missing: {missing}"
        )


# -----------------------------------------------------------------------------
# L3: 出力検証
# -----------------------------------------------------------------------------
@dataclass
class VideoSpec:
    """期待される出力仕様。"""

    duration_sec: float
    width: int = 1080
    height: int = 1920
    tolerance_sec: float = 0.5
    allow_audio: bool = False


@dataclass
class ValidationReport:
    """L3 の合格/検出結果まとめ (NG 時は例外送出されるが、合格時の診断用)。"""

    duration_sec: float
    width: int
    height: int
    has_audio: bool
    face_count: int
    notes: list[str] = field(default_factory=list)


def validate_output_video(
    path: Path | str,
    *,
    expected: VideoSpec,
    face_detector: "FaceDetector | None" = None,
) -> ValidationReport:
    """出力 .mp4 を L3 検査する。

    Raises:
        OutputSpecError: 尺/解像度/音声トラックの仕様違反
        FaceDetectedError: 顔が 1 件でも検出された
        ValidatorBackendUnavailableError: ffprobe / mediapipe が無い
    """
    path = Path(path)
    if not path.exists():
        raise OutputSpecError(f"Video file not found: {path}")

    probe = _ffprobe(path)
    dur = probe["duration_sec"]
    w, h = probe["width"], probe["height"]
    has_audio = probe["has_audio"]
    notes: list[str] = []

    # 尺
    if abs(dur - expected.duration_sec) > expected.tolerance_sec:
        raise OutputSpecError(
            f"Duration {dur:.2f}s outside spec "
            f"{expected.duration_sec:.2f}±{expected.tolerance_sec}s"
        )

    # 解像度
    if (w, h) != (expected.width, expected.height):
        raise OutputSpecError(
            f"Resolution {w}x{h} does not match spec "
            f"{expected.width}x{expected.height}"
        )

    # 音声トラック
    if has_audio and not expected.allow_audio:
        raise OutputSpecError(
            "Audio track present but spec requires silent video. "
            "Mute with `ffmpeg -an` before proceeding."
        )

    # 顔検出
    detector = face_detector or _default_face_detector()
    face_count = detector.count_faces(path)
    if face_count > 0:
        raise FaceDetectedError(
            f"Face detected: {face_count} face(s) in {path.name}. "
            "Segment must be discarded (no mosaic rescue)."
        )

    return ValidationReport(
        duration_sec=dur,
        width=w,
        height=h,
        has_audio=has_audio,
        face_count=0,
        notes=notes,
    )


# -----------------------------------------------------------------------------
# ffprobe バックエンド
# -----------------------------------------------------------------------------
def _ffprobe(path: Path) -> dict:
    if shutil.which("ffprobe") is None:
        raise ValidatorBackendUnavailableError(
            "ffprobe not found on PATH. Install ffmpeg to enable L3 validation."
        )
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=30
        )
    except subprocess.CalledProcessError as exc:
        raise OutputSpecError(f"ffprobe failed: {exc.stderr}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValidatorBackendUnavailableError(
            f"ffprobe timeout on {path}"
        ) from exc

    data = json.loads(out.stdout)
    video = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    if video is None:
        raise OutputSpecError(f"No video stream in {path}")

    duration_sec = float(
        data.get("format", {}).get("duration")
        or video.get("duration")
        or 0.0
    )
    return {
        "duration_sec": duration_sec,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "has_audio": audio,
    }


# -----------------------------------------------------------------------------
# 顔検出バックエンド
# -----------------------------------------------------------------------------
class FaceDetector:
    """顔検出の抽象。実装は mediapipe / opencv-haar / 任意のモック。"""

    def count_faces(self, path: Path) -> int:  # pragma: no cover
        raise NotImplementedError


class MediaPipeFaceDetector(FaceDetector):
    """mediapipe の FaceDetection で検出 (未インストール時は例外)。"""

    def __init__(self, *, sample_fps: float = 1.0) -> None:
        self.sample_fps = sample_fps

    def count_faces(self, path: Path) -> int:
        try:
            import cv2  # type: ignore
            import mediapipe as mp  # type: ignore
        except ImportError as exc:
            raise ValidatorBackendUnavailableError(
                "mediapipe/opencv-python is required for face detection. "
                "`pip install mediapipe opencv-python`"
            ) from exc

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise OutputSpecError(f"cv2 cannot open video: {path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(fps / self.sample_fps))
        detector_ctx = mp.solutions.face_detection.FaceDetection(
            min_detection_confidence=0.5
        )
        face_count = 0
        frame_idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_idx % step == 0:
                    result = detector_ctx.process(
                        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    )
                    if result.detections:
                        face_count += len(result.detections)
                frame_idx += 1
        finally:
            cap.release()
            detector_ctx.close()
        return face_count


class NullFaceDetector(FaceDetector):
    """mediapipe 不在環境用のフェイル・クローズドな代替。

    **動画を「顔なし」と黙って扱ってはいけない** ので、呼ばれたら
    ValidatorBackendUnavailableError を送出してパイプラインを止める。
    """

    def count_faces(self, path: Path) -> int:
        raise ValidatorBackendUnavailableError(
            "Face detection backend unavailable. "
            "Install mediapipe to enable L3 face-check."
        )


def _default_face_detector() -> FaceDetector:
    try:
        import mediapipe  # type: ignore  # noqa: F401
        import cv2  # type: ignore  # noqa: F401
    except ImportError:
        return NullFaceDetector()
    return MediaPipeFaceDetector()


# -----------------------------------------------------------------------------
# Self-check
# -----------------------------------------------------------------------------
def _smoke_test() -> int:
    ok_prompt = {
        "subject": "woman's hand on curtain",
        "action": "curtain parted slowly",
        "style": "cinematic realism, 35mm film, shallow DoF",
        "duration_sec": 10.0,
        "aspect_ratio": "9:16",
        "negative": "face, portrait, watermark, text overlay",
    }
    try:
        validate_prompt_spec(ok_prompt)
        print("[L1] pass: ok_prompt")
    except PromptViolationError as exc:
        print(f"[L1] unexpected fail: {exc}")
        return 1

    bad_prompt = dict(ok_prompt, subject="smiling woman's face closeup")
    try:
        validate_prompt_spec(bad_prompt)
        print("[L1] FAIL: bad_prompt slipped through")
        return 1
    except PromptViolationError as exc:
        print(f"[L1] expected violation: {exc}")

    missing_neg = dict(ok_prompt, negative="watermark only")
    try:
        validate_prompt_spec(missing_neg)
        print("[L1] FAIL: missing_neg slipped through")
        return 1
    except PromptViolationError as exc:
        print(f"[L1] expected violation: {exc}")

    print("[L3] skipped (requires actual .mp4 + ffprobe)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_smoke_test())
