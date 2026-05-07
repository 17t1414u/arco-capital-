"""
Central configuration module.
All other modules import from here — never call os.getenv directly elsewhere.

NOTE: load_dotenv(override=True) is invoked at import time so that values
in .env always take precedence over stale or empty system environment
variables (Windows でシステム環境変数として空の ANTHROPIC_API_KEY が残って
いるケースで、エージェントが起動失敗するのを防ぐ).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# IMPORTANT: override=True ensures .env wins over any pre-existing (possibly
# empty) system environment variables. Do not change without testing on Windows.
load_dotenv(override=True)


class _Settings:
    @property
    def anthropic_api_key(self) -> str:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Copy .env.example to .env and add your key."
            )
        return key

    @property
    def model_name(self) -> str:
        return os.getenv("MODEL_NAME", "anthropic/claude-sonnet-4-6")

    @property
    def temperature(self) -> float:
        return float(os.getenv("TEMPERATURE", "0.7"))

    @property
    def max_tokens(self) -> int:
        return int(os.getenv("MAX_TOKENS", "4096"))

    @property
    def output_dir(self) -> Path:
        return Path(os.getenv("OUTPUT_DIR", "./outputs"))

    # ── Alpaca Trading ─────────────────────────────────────────────────────────
    @property
    def alpaca_api_key(self) -> str:
        return os.getenv("ALPACA_API_KEY", "")

    @property
    def alpaca_secret_key(self) -> str:
        return os.getenv("ALPACA_SECRET_KEY", "")

    @property
    def alpaca_base_url(self) -> str:
        return os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    @property
    def alpaca_data_url(self) -> str:
        return os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")

    @property
    def is_paper_trading(self) -> bool:
        return "paper" in self.alpaca_base_url

    # ── Telegram ───────────────────────────────────────────────────────────────
    @property
    def telegram_bot_token(self) -> str:
        return os.getenv("TELEGRAM_BOT_TOKEN", "")

    @property
    def telegram_chat_id(self) -> str:
        return os.getenv("TELEGRAM_CHAT_ID", "")

    # ── Trading Monitor ────────────────────────────────────────────────────────
    @property
    def poll_interval_seconds(self) -> int:
        return int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

    @property
    def max_watchlist_size(self) -> int:
        return int(os.getenv("MAX_WATCHLIST_SIZE", "10"))

    @property
    def trading_db_path(self) -> Path:
        return Path(os.getenv("TRADING_DB_PATH", "./trading/cache/trading.db"))

    # ── Broker Selection ───────────────────────────────────────────────────────
    @property
    def broker(self) -> str:
        """使用するブローカー: "alpaca" または "moomoo"（デフォルト: alpaca）"""
        return os.getenv("BROKER", "alpaca").lower()

    # ── MooMoo OpenAPI ─────────────────────────────────────────────────────────
    @property
    def moomoo_host(self) -> str:
        """MooMoo OpenD ホスト（ローカルOpenDデーモン）"""
        return os.getenv("MOOMOO_HOST", "127.0.0.1")

    @property
    def moomoo_port(self) -> int:
        """MooMoo OpenD ポート（デフォルト: 11111）"""
        return int(os.getenv("MOOMOO_PORT", "11111"))

    @property
    def moomoo_trade_env(self) -> str:
        """MooMoo 取引環境: "SIMULATE"（模擬）または "REAL"（実取引）"""
        return os.getenv("MOOMOO_TRADE_ENV", "SIMULATE")

    @property
    def moomoo_market(self) -> str:
        """MooMoo 対象マーケット: "US"（米国株）または "HK"（香港株）"""
        return os.getenv("MOOMOO_MARKET", "US")

    @property
    def is_moomoo_simulate(self) -> bool:
        return self.moomoo_trade_env.upper() == "SIMULATE"

    # ── X (Twitter) API ────────────────────────────────────────────────────────
    @property
    def x_api_key(self) -> str:
        """X (Twitter) API Key（Consumer Key）"""
        return os.getenv("X_API_KEY", "")

    @property
    def x_api_secret(self) -> str:
        """X (Twitter) API Secret（Consumer Secret）"""
        return os.getenv("X_API_SECRET", "")

    @property
    def x_access_token(self) -> str:
        """X (Twitter) Access Token"""
        return os.getenv("X_ACCESS_TOKEN", "")

    @property
    def x_access_token_secret(self) -> str:
        """X (Twitter) Access Token Secret"""
        return os.getenv("X_ACCESS_TOKEN_SECRET", "")

    @property
    def x_bearer_token(self) -> str:
        """X (Twitter) Bearer Token（読み取り専用用途）"""
        return os.getenv("X_BEARER_TOKEN", "")

    @property
    def x_account_handle(self) -> str:
        """X アカウントハンドル（@ なし）"""
        return os.getenv("X_ACCOUNT_HANDLE", "RR1420597468366")

    # ── Google AI (Nano Banana Pro) ────────────────────────────────────────────
    @property
    def google_api_key(self) -> str:
        """Google AI Studio API Key（Nano Banana Pro 画像生成用）"""
        return os.getenv("GOOGLE_API_KEY", "")

    # ── 資産運用事業部 ──────────────────────────────────────────────────────────
    @property
    def investment_division_dir(self) -> Path:
        """資産運用事業部のドキュメントルートディレクトリ"""
        return Path(os.getenv(
            "INVESTMENT_DIVISION_DIR",
            "./ArcoCapital/資産運用事業部"
        ))

    @property
    def max_position_pct(self) -> float:
        """1銘柄の最大ポジションサイズ（総資産に対する割合、デフォルト: 10%）"""
        return float(os.getenv("MAX_POSITION_PCT", "0.10"))

    @property
    def stop_loss_pct(self) -> float:
        """デフォルトのストップロス幅（デフォルト: 5%）"""
        return float(os.getenv("STOP_LOSS_PCT", "0.05"))

    @property
    def take_profit_pct(self) -> float:
        """デフォルトの利確幅（デフォルト: 10%）"""
        return float(os.getenv("TAKE_PROFIT_PCT", "0.10"))


settings = _Settings()
