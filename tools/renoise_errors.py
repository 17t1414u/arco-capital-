"""Renoise 呼び出し時の例外階層。

設計書 ArcoCapital/経営陣/Renoise例外処理設計書.md §4.2 準拠。

AGENTS.md RULE-04 (サイレントフォールバック禁止):
  呼び出し元は RenoiseError を広く except せず、必ず個別 except で扱うこと。
  唯一の例外: Director 層の最上位で `RenoiseError` を捕捉し
  operations/renoise_errors.jsonl への構造化記録 + Kill-switch 判定を行う。
"""

from __future__ import annotations


class RenoiseError(RuntimeError):
    """Renoise 関連エラーの基底。Director 最上位のみ捕捉可。"""


class PromptViolationError(RenoiseError):
    """L1: プロンプト仕様違反 (顔指定禁止/尺範囲/解像度等)。

    送出元: tools.renoise_validator.validate_prompt_spec
    対処: 自動補正せず停止 (RULE-04)。
    """


class RenoiseTimeoutError(RenoiseError):
    """L2: 単一試行がタイムアウト上限を超過。

    送出元: tools.renoise_client.call_renoise_with_guards
    対処: L2 リトライ機構が指数バックオフで再試行。
    """


class RenoiseRetryExhaustedError(RenoiseError):
    """L2: リトライ上限 (通常 2 回 + 初回 = 3 試行) を使い切った。

    Kill-switch 連動: 同一日内 3 回発生で misfire_detected トリガ。
    対処: 該当プロジェクトは Mode A 降格。人間判断待ち。
    """


class CircuitOpenError(RenoiseError):
    """L2: サーキットブレーカが OPEN 状態 (15 分間 全生成停止)。

    発火条件: 直近 10 分で連続 3 回失敗。
    Kill-switch 連動: 24h 以内 2 回発生で misfire_detected トリガ。
    """


class FaceDetectedError(RenoiseError):
    """L3: 出力動画から顔ランドマーク検出。

    送出元: tools.renoise_validator.validate_output_video
    対処: 該当セグメント破棄。モザイク救済禁止 (設計書 §3.3)。
    """


class BudgetExhaustedError(RenoiseError):
    """L2: セグメント単価上限 (¥4,000) または週次上限 (¥10,000) 到達。

    対処: 起動前に停止。project.json を status: "blocked" に書換。
    """


class OutputSpecError(RenoiseError):
    """L3: 出力動画が仕様外 (尺・解像度・音声トラック等)。

    送出元: tools.renoise_validator.validate_output_video
    対処: 該当セグメント破棄。再生成キュー投入は別途判断。
    """


class ValidatorBackendUnavailableError(RenoiseError):
    """L1/L3 検証バックエンド (mediapipe / ffprobe) が利用不可。

    発生例: ffprobe が PATH にない、mediapipe 未インストール。
    対処: 結果を未検証のまま流さず、運用を停止してバックエンドを整備する。
    """
