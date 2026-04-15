"""
Telegram bot interface — Phase 1.

Commands:
  /start              — welcome message
  /watch AAPL 170     — set a price alert
  /watch NVDA above 900
  /watch TSLA rsi below 30
  /alerts             — list active alerts
  /cancel <id>        — cancel an alert
  /price AAPL         — check latest price
  /status             — show watchlist + system status

Alerts are stored in SQLite and polled by the MonitorCrew.
Outbound alert messages are sent via send_alert().
"""

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config.settings import settings
from trading.cache.ohlcv import save_alert, get_active_alerts, deactivate_alert
from trading.interface.command_parser import parse_watch_command
from trading.tools.market_data import get_latest_price

logger = logging.getLogger(__name__)


# ── Outbound helper ────────────────────────────────────────────────────────────

async def send_alert(message: str, bot_app: Optional[Application] = None) -> None:
    """
    Send an alert message to the configured Telegram chat.
    Can be called from outside the bot (e.g., from MonitorCrew).
    """
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured — alert not sent: %s", message)
        print(f"[ALERT] {message}")
        return

    if bot_app:
        await bot_app.bot.send_message(chat_id=settings.telegram_chat_id, text=message)
    else:
        from telegram import Bot
        async with Bot(token=settings.telegram_bot_token) as bot:
            await bot.send_message(chat_id=settings.telegram_chat_id, text=message)


# ── Command handlers ───────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Trading Agent online.\n\n"
        "Commands:\n"
        "  /watch AAPL 170         — alert when AAPL < $170\n"
        "  /watch NVDA above 900   — alert when NVDA > $900\n"
        "  /watch TSLA rsi below 30\n"
        "  /alerts                 — list active alerts\n"
        "  /cancel <id>            — cancel alert by ID\n"
        "  /price AAPL             — latest price\n"
        "  /status                 — system status\n"
    )


async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    spec = parse_watch_command(text)
    if spec is None:
        await update.message.reply_text(
            "Could not parse alert. Examples:\n"
            "  /watch AAPL 170\n"
            "  /watch NVDA above 900\n"
            "  /watch TSLA rsi below 30"
        )
        return

    alert_id = await save_alert(spec.ticker, spec.condition_type, spec.threshold)
    condition_desc = spec.condition_type.replace("_", " ")
    await update.message.reply_text(
        f"Alert #{alert_id} set: {spec.ticker} {condition_desc} {spec.threshold}"
    )


async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    alerts = await get_active_alerts()
    if not alerts:
        await update.message.reply_text("No active alerts.")
        return

    lines = ["Active alerts:"]
    for a in alerts:
        cond = a["condition_type"].replace("_", " ")
        lines.append(f"  #{a['id']} {a['ticker']} {cond} {a['threshold']}")
    await update.message.reply_text("\n".join(lines))


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /cancel <alert_id>")
        return
    try:
        alert_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID. Usage: /cancel 3")
        return

    await deactivate_alert(alert_id)
    await update.message.reply_text(f"Alert #{alert_id} cancelled.")


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /price AAPL")
        return
    ticker = context.args[0].upper()
    price = await get_latest_price(ticker)
    if price is None:
        await update.message.reply_text(f"Could not fetch price for {ticker}.")
    else:
        await update.message.reply_text(f"{ticker}: ${price:.2f}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    alerts = await get_active_alerts()
    mode = "PAPER" if settings.is_paper_trading else "LIVE"
    await update.message.reply_text(
        f"System status:\n"
        f"  Mode:           {mode}\n"
        f"  Active alerts:  {len(alerts)}\n"
        f"  Poll interval:  {settings.poll_interval_seconds}s\n"
    )


# ── Application factory ────────────────────────────────────────────────────────

def build_application() -> Application:
    if not settings.telegram_bot_token:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN is not set in .env")

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("watch", cmd_watch))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("status", cmd_status))
    return app


def run_bot() -> None:
    """Start the bot in polling mode (blocking)."""
    app = build_application()
    logger.info("Telegram bot polling started.")
    app.run_polling()
