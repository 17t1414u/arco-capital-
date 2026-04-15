"""
Trading Department Agents — 資産運用事業部エージェント群

Agents:
  InvestmentAnalystAgent — 銘柄総合分析・BUY/SELL/HOLDシグナル生成
  StrategyEngineerAgent  — 売買戦略のバックテスト・ハーネス改善
  SNSReporterAgent       — 投資情報・実績のSNSコンテンツ生成

Note: 注文執行は既存の trading/agents/trader.py を使用する。
"""

from agents.trading.investment_analyst import InvestmentAnalystAgent
from agents.trading.strategy_engineer import StrategyEngineerAgent
from agents.trading.sns_reporter import SNSReporterAgent

__all__ = [
    "InvestmentAnalystAgent",
    "StrategyEngineerAgent",
    "SNSReporterAgent",
]
