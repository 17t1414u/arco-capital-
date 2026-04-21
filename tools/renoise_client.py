"""Renoise L2 実行境界ラッパ。

Renoise 例外処理設計書 v0.1 §3.2 準拠:
  - タイムアウト 120 秒/セグメント
  - リトライ上限 2 回 (合計 3 試行) + 指数バックオフ (2s → 4s → 8s)
  - セグメント単価上限 ¥4,000、週次予算 ¥10,000
  - サーキットブレーカ: 直近 10 分で 3 回失敗 → 15 分停止
  - 同一プロンプト連投禁止 (摂動必須)

AGENTS.md RULE-04 準拠: エラーは隠蔽せず必ず operations/renoise_errors.jsonl
に構造化記録し、上位 Director で処理させる。

MCP 差し替えポイント:
  RenoiseInvoker プロトコルを差し替えることで、MockRenoiseInvoker (現行) から
  renoise:director / renoise:renoise-gen を直接叩く実装へ切り替え可能。
"""

from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Protocol

from tools.renoise_errors import (
    BudgetExhaustedError,
    CircuitOpenError,
    RenoiseRetryExhaustedError,
    RenoiseTimeoutError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ERROR_LOG = REPO_ROOT / "operations" / "renoise_errors.jsonl"

# -----------------------------------------------------------------------------
# 定数 (設計書 §3.2)
# -----------------------------------------------------------------------------
DEFAULT_TIMEOUT_SEC = 120.0
DEFAULT_MAX_RETRIES = 2               # 合計 3 試行
BACKOFF_BASE_SEC = 2.0                # 2s → 4s → 8s
SEGMENT_COST_CAP_JPY = 4_000
WEEKLY_COST_CAP_JPY = 10_000

CIRCUIT_WINDOW_SEC = 600              # 10 分
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_OPEN_SEC = 900                # 15 分停止


# -----------------------------------------------------------------------------
# MCP Invoker プロトコル
# -----------------------------------------------------------------------------
class RenoiseInvoker(Protocol):
    """Renoise MCP 呼び出しの抽象インタフェース。

    実装例:
      - MockRenoiseInvoker (本ファイル): 開発・テスト用
      - RealRenoiseInvoker (未実装): renoise:renoise-gen を実呼出し
    """

    def invoke(self, prompt: dict, *, timeout_sec: float) -> dict:
        """指定プロンプトで動画生成。

        Returns:
            {"video_path": str, "cost_jpy": int, "duration_sec": float,
             "request_id": str}
        Raises:
            RenoiseTimeoutError: タイムアウト
            Exception: 任意の Renoise 側エラー (再試行判定は呼出元)
        """


class MockRenoiseInvoker:
    """モック実装 — 実 MCP 差し替え前の開発・テスト用。

    挙動:
      - duration_sec に比例して sleep
      - fail_probability で確率的に失敗
      - 成功時は ダミー mp4 パス + ¥3,000〜¥4,000 のランダムコストを返す
    """

    def __init__(
        self,
        *,
        fail_probability: float = 0.0,
        latency_sec: float = 1.5,
        deterministic_seed: int | None = None,
    ) -> None:
        self.fail_probability = fail_probability
        self.latency_sec = latency_sec
        self._rng = random.Random(deterministic_seed)

    def invoke(self, prompt: dict, *, timeout_sec: float) -> dict:
        elapsed = 0.0
        step = 0.25
        while elapsed < self.latency_sec and elapsed < timeout_sec:
            time.sleep(step)
            elapsed += step
        if elapsed >= timeout_sec:
            raise RenoiseTimeoutError(
                f"MockRenoiseInvoker timed out after {elapsed:.1f}s "
                f"(cap={timeout_sec:.1f}s)"
            )
        if self._rng.random() < self.fail_probability:
            raise RuntimeError("MockRenoiseInvoker synthetic failure")

        segment_id = prompt.get("segment_id", "S?")
        cost = self._rng.randint(3_000, 4_000)
        return {
            "video_path": f"outputs/sns_video/mock_{segment_id}.mp4",
            "cost_jpy": cost,
            "duration_sec": prompt.get("duration_sec", 10.0),
            "request_id": f"mock-{self._rng.randint(10**9, 10**10 - 1)}",
        }


# -----------------------------------------------------------------------------
# サーキットブレーカ
# -----------------------------------------------------------------------------
@dataclass
class CircuitBreaker:
    """10 分窓で 3 回連続失敗 → 15 分オープン (設計書 §3.2)。"""

    window_sec: int = CIRCUIT_WINDOW_SEC
    failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD
    open_sec: int = CIRCUIT_OPEN_SEC
    _failures: deque[float] = field(default_factory=deque)
    _opened_at: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def check(self, *, now: float | None = None) -> None:
        """Open ならば CircuitOpenError を送出。"""
        now = now if now is not None else time.time()
        with self._lock:
            if self._opened_at is not None:
                if now - self._opened_at < self.open_sec:
                    remaining = self.open_sec - (now - self._opened_at)
                    raise CircuitOpenError(
                        f"Circuit open for another {remaining:.0f}s"
                    )
                # 冷却完了 → 半開 (1 回試行させて成否で閉開判定)
                self._opened_at = None
                self._failures.clear()

    def record_failure(self, *, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        with self._lock:
            self._failures.append(now)
            # 窓外を捨てる
            while self._failures and now - self._failures[0] > self.window_sec:
                self._failures.popleft()
            if len(self._failures) >= self.failure_threshold:
                self._opened_at = now

    def record_success(self) -> None:
        with self._lock:
            self._failures.clear()
            self._opened_at = None


# プロセス内共有シングルトン
_GLOBAL_BREAKER = CircuitBreaker()


# -----------------------------------------------------------------------------
# 予算チェック
# -----------------------------------------------------------------------------
def _ensure_segment_budget(prompt: dict) -> None:
    est_jpy = int(prompt.get("estimated_cost_jpy", 0))
    if est_jpy > SEGMENT_COST_CAP_JPY:
        raise BudgetExhaustedError(
            f"Estimated cost ¥{est_jpy:,} exceeds per-segment cap "
            f"¥{SEGMENT_COST_CAP_JPY:,}"
        )


def _ensure_weekly_budget(
    *, current_weekly_spend_jpy: int, segment_estimate_jpy: int
) -> None:
    remaining = WEEKLY_COST_CAP_JPY - current_weekly_spend_jpy
    needed = max(segment_estimate_jpy, SEGMENT_COST_CAP_JPY)
    if remaining < needed:
        raise BudgetExhaustedError(
            f"Weekly Renoise budget remaining ¥{remaining:,} < needed ¥{needed:,}"
        )


# -----------------------------------------------------------------------------
# プロンプトハッシュ (連投検知用)
# -----------------------------------------------------------------------------
def _prompt_hash(prompt: dict) -> str:
    canonical = json.dumps(prompt, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


_RECENT_HASHES: set[str] = set()
_RECENT_HASHES_LOCK = threading.Lock()


def _reject_duplicate_prompt(prompt: dict) -> str:
    h = _prompt_hash(prompt)
    with _RECENT_HASHES_LOCK:
        if h in _RECENT_HASHES:
            raise BudgetExhaustedError(
                "Identical prompt already submitted this session — perturb required"
            )
        _RECENT_HASHES.add(h)
    return h


def clear_prompt_cache() -> None:
    """テストとセッション切替用。"""
    with _RECENT_HASHES_LOCK:
        _RECENT_HASHES.clear()


# -----------------------------------------------------------------------------
# エラーログ
# -----------------------------------------------------------------------------
def _log_error(record: dict) -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
        **record,
    }
    with ERROR_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# -----------------------------------------------------------------------------
# 公開 API
# -----------------------------------------------------------------------------
def call_renoise_with_guards(
    prompt: dict,
    *,
    project_slug: str,
    segment_id: str,
    current_weekly_spend_jpy: int = 0,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    max_retries: int = DEFAULT_MAX_RETRIES,
    invoker: RenoiseInvoker | None = None,
    breaker: CircuitBreaker | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Renoise を L2 境界で包んで呼び出す。

    Args:
        prompt: L1 validator を通過済みのプロンプト辞書。
                `segment_id` `duration_sec` `estimated_cost_jpy` を含むこと。
        project_slug: ArcoCapital/SNS動画運用事業部/企画/<slug>
        segment_id: "S1" / "S2" / "S3" など
        current_weekly_spend_jpy: 週次累積消費額 (BudgetTracker から渡す)
        timeout_sec: 単一試行タイムアウト (default 120s)
        max_retries: 追加試行回数 (default 2 = 合計 3 試行)
        invoker: MCP 実装 (未指定時は MockRenoiseInvoker)
        breaker: プロセス共有サーキットブレーカ
        sleep: テスト用注入ポイント

    Returns:
        invoker.invoke() の戻り値と同形式 (video_path / cost_jpy / ...)

    Raises:
        BudgetExhaustedError: 予算上限 or 同一プロンプト連投
        CircuitOpenError: サーキット OPEN
        RenoiseTimeoutError: 最終試行もタイムアウト
        RenoiseRetryExhaustedError: 全試行失敗
    """
    invoker = invoker or MockRenoiseInvoker()
    breaker = breaker or _GLOBAL_BREAKER

    # -- 起動前ガード --
    breaker.check()
    _ensure_segment_budget(prompt)
    _ensure_weekly_budget(
        current_weekly_spend_jpy=current_weekly_spend_jpy,
        segment_estimate_jpy=int(prompt.get("estimated_cost_jpy", SEGMENT_COST_CAP_JPY)),
    )
    prompt_h = _reject_duplicate_prompt(prompt)

    attempts = max_retries + 1
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        start = time.time()
        try:
            result = invoker.invoke(prompt, timeout_sec=timeout_sec)
        except RenoiseTimeoutError as exc:
            elapsed = time.time() - start
            _log_error(
                {
                    "layer": "L2",
                    "error": "RenoiseTimeoutError",
                    "project_slug": project_slug,
                    "segment": segment_id,
                    "attempt": attempt,
                    "elapsed_sec": round(elapsed, 2),
                    "prompt_hash": prompt_h,
                }
            )
            last_exc = exc
            breaker.record_failure()
        except Exception as exc:  # RULE-04: 次の except で包むのみ
            elapsed = time.time() - start
            _log_error(
                {
                    "layer": "L2",
                    "error": type(exc).__name__,
                    "error_message": str(exc),
                    "project_slug": project_slug,
                    "segment": segment_id,
                    "attempt": attempt,
                    "elapsed_sec": round(elapsed, 2),
                    "prompt_hash": prompt_h,
                }
            )
            last_exc = exc
            breaker.record_failure()
        else:
            breaker.record_success()
            result["attempt"] = attempt
            result["prompt_hash"] = prompt_h
            return result

        # リトライ継続可否判定
        if attempt >= attempts:
            break
        try:
            breaker.check()  # リトライ前にもサーキット判定
        except CircuitOpenError:
            _log_error(
                {
                    "layer": "L2",
                    "error": "CircuitOpenError",
                    "project_slug": project_slug,
                    "segment": segment_id,
                    "attempt_attempted_next": attempt + 1,
                    "prompt_hash": prompt_h,
                }
            )
            raise
        sleep(BACKOFF_BASE_SEC * (2 ** (attempt - 1)))

    # 全試行失敗
    _log_error(
        {
            "layer": "L2",
            "error": "RenoiseRetryExhaustedError",
            "project_slug": project_slug,
            "segment": segment_id,
            "attempts": attempts,
            "prompt_hash": prompt_h,
            "last_error": type(last_exc).__name__ if last_exc else "Unknown",
        }
    )
    raise RenoiseRetryExhaustedError(
        f"Renoise failed {attempts} times for {project_slug}/{segment_id} "
        f"(last: {type(last_exc).__name__ if last_exc else 'Unknown'})"
    ) from last_exc


# -----------------------------------------------------------------------------
# Smoke test / CLI エントリ
# -----------------------------------------------------------------------------
def _smoke_test() -> int:
    """開発時の疎通確認。`python -m tools.renoise_client` で実行。"""
    sample_prompt = {
        "segment_id": "S1",
        "subject": "woman's hand touching sheer curtain",
        "style": "cinematic realism, 35mm film",
        "duration_sec": 10.0,
        "estimated_cost_jpy": 3500,
        "negative": "face, portrait, watermark, text overlay",
    }
    clear_prompt_cache()
    invoker = MockRenoiseInvoker(latency_sec=0.3, deterministic_seed=42)
    result = call_renoise_with_guards(
        sample_prompt,
        project_slug="cinematic-everyday-01",
        segment_id="S1",
        current_weekly_spend_jpy=0,
        invoker=invoker,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_smoke_test())
