# Virtual Company — AI Multi-Agent System

50人規模のAIエージェントが自律的に連携する「仮想会社」。
CrewAI の階層的プロセスを使い、実際の企業組織を模した意思決定・業務実行システムです。

---

## アーキテクチャ概念図

```
                    ┌─────────────┐
                    │     CEO     │  ← manager_agent (意思決定・委任)
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
     ┌─────▼─────┐   ┌─────▼─────┐   ┌────▼──────┐
     │    CTO    │   │    COO    │   │    CFO    │   (Phase 2+)
     └─────┬─────┘   └─────┬─────┘   └────┬──────┘
           │               │               │
  ┌────────▼───┐  ┌────────▼───┐  ┌────────▼───┐
  │Engineering │  │ Marketing  │  │   Finance  │   (Phase 3+)
  │  (6名)     │  │  (5名)     │  │  (4名)     │
  └────────────┘  └────────────┘  └────────────┘
```

---

## フェーズ1スコープ (現在実装済み)

| 項目 | 内容 |
|------|------|
| CEOエージェント | 会社の目標設定・最終意思決定 |
| CTOエージェント | 技術的方向性の評価・提言 |
| 初回テスト | 「最初に取り組むべきビジネス」の議論 |
| 出力 | `outputs/discussion_result.md` |

---

## ディレクトリ構造

```
virtual_company/
├── main.py                      # エントリーポイント
├── requirements.txt             # 依存ライブラリ
├── .env.example                 # 環境変数テンプレート
├── .gitignore
├── README.md
│
├── config/
│   ├── settings.py              # 全設定の一元管理 (env読み込み)
│   └── llm.py                   # LLMファクトリ → 全エージェントが参照
│
├── agents/
│   ├── base_agent.py            # BaseAgent 抽象クラス
│   ├── executive/               # ✅ Phase 1: CEO, CTO
│   │   ├── ceo.py
│   │   └── cto.py
│   ├── engineering/             # 🔲 Phase 2: Lead, BE, FE, DevOps, QA, Security
│   ├── marketing/               # 🔲 Phase 3: Lead, Content, SEO, Growth, Analytics
│   ├── sales/                   # 🔲 Phase 3: Lead, AE, SDR, Customer Success
│   ├── product/                 # 🔲 Phase 2: PM, UX, Data Analyst
│   ├── operations/              # 🔲 Phase 4: HR, Legal, Finance, Admin
│   └── support/                 # 🔲 Phase 4: Lead, Tier1, Tier2
│
├── tasks/
│   ├── base_task.py             # make_task() ヘルパー
│   └── executive/
│       └── strategy_tasks.py    # ✅ Phase 1: CTO分析 + CEO決定タスク
│
├── crews/
│   ├── base_crew.py             # BaseCrew (build/run 抽象)
│   └── executive/
│       └── executive_crew.py    # ✅ Phase 1: 階層的 CEO+CTO Crew
│
└── outputs/
    └── discussion_result.md     # 実行結果 (gitignore対象)
```

---

## セットアップ

### 1. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を開き、Anthropic API キーを設定:

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
```

### 2. 依存ライブラリのインストール

Python 3.11 以上を推奨します。

```bash
pip install -r requirements.txt
```

### 3. 実行

```bash
python main.py
```

---

## 出力の読み方

実行完了後、`outputs/discussion_result.md` に以下が出力されます:

1. **CTOの市場分析** — 3つのビジネスドメイン候補と技術評価
2. **CEOの最終決定** — 選定したビジネス方向性・ミッション・ネクストステップ

コンソールには CrewAI のエージェント推論ステップがリアルタイムで表示されます。

---

## 新しいエージェントの追加方法

### ステップ1: エージェントファイルの作成

```python
# agents/engineering/backend.py
from agents.base_agent import BaseAgent

class BackendEngineerAgent(BaseAgent):
    role = "Senior Backend Engineer"
    goal = "..."
    backstory = "..."
    allow_delegation = False
```

### ステップ2: タスクの追加

```python
# tasks/engineering/dev_tasks.py
from tasks.base_task import make_task

def build_dev_tasks(backend_agent, ...):
    return [make_task(..., agent=backend_agent)]
```

### ステップ3: Crewへの組み込み

```python
# crews/engineering/engineering_crew.py
from crews.base_crew import BaseCrew
from agents.engineering.backend import BackendEngineerAgent

class EngineeringCrew(BaseCrew):
    def build(self):
        backend = BackendEngineerAgent.build()
        ...
```

---

## 50エージェント 部門別ロードマップ

| フェーズ | 部門 | エージェント | 人数 |
|----------|------|------------|------|
| Phase 1 ✅ | Executive | CEO, CTO | 2 |
| Phase 2 | Executive | COO, CFO, CMO, CPO | 4 |
| Phase 2 | Engineering | Lead Engineer, Backend×2, Frontend×2, DevOps, QA, Security | 8 |
| Phase 2 | Product | Product Manager, UX Designer, Data Analyst | 3 |
| Phase 3 | Marketing | Marketing Lead, Content×2, SEO, Growth, Analytics | 6 |
| Phase 3 | Sales | Sales Lead, AE×2, SDR×2, Customer Success×2 | 7 |
| Phase 4 | Operations | HR, Legal, Finance×2, Admin | 5 |
| Phase 4 | Support | Support Lead, Tier1×3, Tier2×2 | 6 |
| Phase 5 | Cross-dept | R&D, Strategy, Partnerships, PR, Compliance | 5 |
| **合計** | | | **46** |

---

## 技術的意思決定の根拠

### なぜ CrewAI か

- **組織比喩の自然なマッピング**: Agent/Task/Crew が役職/業務/チームに対応し、コードが読みやすい
- **階層的プロセスのネイティブサポート**: `Process.hierarchical` + `manager_agent` で CEO委任構造を自然に表現
- **Claude との統合**: LiteLLM 経由でシームレスに動作

### なぜ `Process.hierarchical` か

- CEOが全タスクを俯瞰し、適切なエージェントへ動的に委任できる
- Sequential とは異なり、CEOが文脈を持ちながら複数エージェントを調整できる
- 将来50エージェントになっても同じパターンでスケール可能

### なぜ `claude-sonnet-4-6` か

- 高度な推論能力でエージェント間の複雑な調整タスクを処理
- ツール使用の精度が高く、CrewAI の委任ループに適合
- 入出力トークンのコスト効率が良く、50エージェント規模での運用コストを抑制

---

## トラブルシューティング

| エラー | 原因 | 対処 |
|--------|------|------|
| `AuthenticationError` | API キー未設定 | `.env` に `ANTHROPIC_API_KEY` を設定 |
| `ValueError: manager_agent cannot be in agents list` | CEOが`agents=[]`に含まれている | `executive_crew.py` の `agents=[]` からCEOを除く |
| `BadRequestError: max_tokens` | Anthropic API の必須パラメータ未設定 | `config/llm.py` で `max_tokens=4096` を確認 |
| `ModuleNotFoundError: crewai` | 依存関係未インストール | `pip install -r requirements.txt` を実行 |
| 出力ファイルが生成されない | `outputs/` ディレクトリが存在しない | `tasks/base_task.py` の `mkdir` が呼ばれているか確認 |

---

## ライセンス

MIT
