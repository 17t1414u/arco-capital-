"""
Virtual Company — Phase 1 Entry Point

CEO と CTO が「この仮想会社が最初に取り組むべきビジネス」について議論し、
意思決定結果を outputs/discussion_result.md に出力します。

Usage:
    python main.py

Prerequisites:
    1. Copy .env.example to .env
    2. Set ANTHROPIC_API_KEY in .env
    3. pip install -r requirements.txt
"""

# load_dotenv() must be called BEFORE any CrewAI imports,
# because CrewAI reads environment variables at import time.
from dotenv import load_dotenv

load_dotenv(override=True)  # .env が空のシステム環境変数より優先されるように

from config.settings import settings  # noqa: E402 (intentional post-dotenv import)
from crews.executive.executive_crew import ExecutiveCrew  # noqa: E402


def main() -> None:
    output_path = settings.output_dir / "discussion_result.md"

    print("=" * 64)
    print("  Virtual Company — Executive Strategy Session")
    print("  Phase 1: ビジネス方向性の議論")
    print("=" * 64)
    print(f"  Model  : {settings.model_name}")
    print(f"  Output : {output_path}")
    print("=" * 64)
    print()

    crew = ExecutiveCrew()
    result = crew.run()

    print()
    print("=" * 64)
    print("  DISCUSSION COMPLETE / 議論完了")
    print("=" * 64)
    print(result)
    print()
    print(f"Full result saved to: {output_path}")


if __name__ == "__main__":
    main()
