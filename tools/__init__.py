"""Arco Capital 共通ツール層。

Renoise / ffmpeg / mediapipe などの外部ツール呼び出しを、
L1 (構文) / L2 (実行境界) / L3 (結果検証) の3層防御で包んで提供する。

設計根拠: ArcoCapital/経営陣/Renoise例外処理設計書.md
"""

from tools.renoise_errors import (  # noqa: F401
    RenoiseError,
    PromptViolationError,
    RenoiseTimeoutError,
    RenoiseRetryExhaustedError,
    CircuitOpenError,
    FaceDetectedError,
    BudgetExhaustedError,
    OutputSpecError,
    ValidatorBackendUnavailableError,
)
