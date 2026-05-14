"""Load operational guardrails from operations/guardrails.yaml.

本モジュールはボードルーム決議 (.octogent/decision.md) の執行レイヤー。
モード判定 / 事業部別設定参照 / Phase 1 ゲート判定 を提供する。

Usage:
    from operations import load_guardrails, ModeManager

    rules = load_guardrails()
    mm = ModeManager(rules)
    if mm.can_send_external("sns_video"):
        ...  # 事業部が外部送信を許可されているか
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise RuntimeError(
        "PyYAML が必要です。pip install pyyaml を実行してください。"
    ) from e


GUARDRAILS_PATH = Path(__file__).resolve().parent / "guardrails.yaml"


@dataclass(frozen=True)
class Guardrails:
    raw: dict[str, Any]

    @property
    def active_mode(self) -> str:
        return str(self.raw["active_mode"])

    @property
    def phase(self) -> int:
        return int(self.raw["phase"])

    def mode_config(self, mode: str | None = None) -> dict[str, Any]:
        mode = mode or self.active_mode
        return dict(self.raw["modes"][mode])

    def division(self, key: str) -> dict[str, Any]:
        return dict(self.raw["divisions"][key])

    def budget(self, bucket: str) -> dict[str, Any]:
        return dict(self.raw["budget"][bucket])


def load_guardrails(path: Path | str = GUARDRAILS_PATH) -> Guardrails:
    """guardrails.yaml を読み込む。ファイル欠落は ``FileNotFoundError``。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Guardrails file not found: {p}. Run Phase 0 setup first."
        )
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Malformed guardrails.yaml at {p}")
    return Guardrails(raw=data)


class ModeManager:
    """事業部単位のモード判定ヘルパ。

    RULE-04 に従い、未定義事業部・未知モード参照は例外を投げる (フォールバック禁止)。
    """

    def __init__(self, guardrails: Guardrails):
        self.g = guardrails

    def division_mode(self, division_key: str) -> str:
        return str(self.g.division(division_key)["mode"])

    def can_send_external(self, division_key: str) -> bool:
        mode = self.division_mode(division_key)
        return bool(self.g.mode_config(mode)["external_send_allowed"])

    def requires_approval(self, division_key: str) -> bool:
        mode = self.division_mode(division_key)
        return bool(self.g.mode_config(mode)["human_approval_required"])

    def dm_sla_hours(self, division_key: str) -> int:
        div = self.g.division(division_key)
        return int(div["sla"]["dm_response_hours"])

    def phase_1_gate_criteria(self, division_key: str) -> list[str]:
        return list(self.g.division(division_key)["phase_1_gate"])
