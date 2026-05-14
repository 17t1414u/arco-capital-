"""
Knowledge Department Agents — ナレッジ連携事業部エージェント群

Agents:
  KnowledgeDirectorAgent — 事業部長 (manager_agent)
  KnowledgeCuratorAgent  — 素材取り込み・分類
  SynthesisAnalystAgent  — 複数ソース横断分析・洞察抽出
  TemplateAuthorAgent    — 商品化ドキュメント・LP執筆
"""

from agents.knowledge.curator import KnowledgeCuratorAgent
from agents.knowledge.director import KnowledgeDirectorAgent
from agents.knowledge.synthesis_analyst import SynthesisAnalystAgent
from agents.knowledge.template_author import TemplateAuthorAgent

__all__ = [
    "KnowledgeDirectorAgent",
    "KnowledgeCuratorAgent",
    "SynthesisAnalystAgent",
    "TemplateAuthorAgent",
]
