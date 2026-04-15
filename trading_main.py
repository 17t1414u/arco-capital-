"""
Trading Agent — Entry Point

Usage:
    python trading_main.py --phase 1              # Phase 1: alert monitor
    python trading_main.py --phase 1 --dry-run    # Phase 1: dry run (no Telegram/DB writes)
    python trading_main.py --phase 2 --ticker AAPL  # Phase 2: analyse & trade one ticker
    python trading_main.py --analyse AAPL           # On-demand LLM analysis

Prerequisites:
    1. pip install -r requirements.txt
    2. Copy .env.example to .env and fill in ALPACA_* and TELEGRAM_* keys
    3. python trading_main.py --phase 1

WARNING:
    ALPACA_BASE_URL defaults to the paper trading endpoint.
    Set ALPACA_BASE_URL=https://api.alpaca.markets ONLY when you are ready for live trading.
"""

import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Stock Trading Agent")
    parser.add_argument("--phase", type=int, choices=[1, 2], default=1,
                        help="Run phase: 1=alert monitor, 2=full auto trading")
    parser.add_argument("--dry-run", action="store_true",
                        help="Phase 1: evaluate conditions without sending alerts or writing DB")
    parser.add_argument("--ticker", type=str, default=None,
                        help="Phase 2: ticker to analyse and trade")
    parser.add_argument("--analyse", type=str, default=None,
                        help="Run on-demand LLM analysis for a ticker and exit")
    args = parser.parse_args()

    from config.settings import settings

    print("=" * 64)
    print("  Trading Agent")
    print(f"  Phase   : {args.phase}")
    print(f"  Mode    : {'DRY RUN' if args.dry_run else ('PAPER' if settings.is_paper_trading else 'LIVE ⚠️')}")
    print(f"  Alpaca  : {settings.alpaca_base_url}")
    print("=" * 64)

    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        logger.error("ALPACA_API_KEY / ALPACA_SECRET_KEY not set in .env — aborting.")
        sys.exit(1)

    if args.analyse:
        from trading.crews.monitor_crew import MonitorCrew
        crew = MonitorCrew(dry_run=True)
        result = crew.analyse_ticker(args.analyse.upper())
        print(result)
        return

    if args.phase == 1:
        from trading.crews.monitor_crew import MonitorCrew
        crew = MonitorCrew(dry_run=args.dry_run)
        crew.run(with_telegram=not args.dry_run)

    elif args.phase == 2:
        if not args.ticker:
            logger.error("--ticker is required for phase 2. Example: --phase 2 --ticker AAPL")
            sys.exit(1)
        from trading.crews.trading_crew import TradingCrew
        crew = TradingCrew()
        result = crew.run_signal(args.ticker.upper())
        print(result)


if __name__ == "__main__":
    main()
