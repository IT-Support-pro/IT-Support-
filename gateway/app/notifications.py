import asyncio
import logging
from typing import Optional
import httpx
from app.config import settings

logger = logging.getLogger("hbk.notifications")

async def send_telegram_message(message: str) -> bool:
    """Send text message to configured Telegram bot and chat ID asynchronously without blocking."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                logger.warning(f"Telegram send failed ({res.status_code}): {res.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Telegram notification error: {e}")
        return False

def notify_alert_firing(device_id: str, store_code: str, message: str):
    """Template: 🔴 {device_id} ({store}) - {message}"""
    text = f"🔴 <b>{device_id}</b> ({store_code}) - {message}"
    try:
        asyncio.create_task(send_telegram_message(text))
    except RuntimeError:
        # No event loop in current context
        pass

def notify_alert_resolved(device_id: str, rule_key: str):
    """Template: 🟢 {device_id} - {rule} back to normal"""
    text = f"🟢 <b>{device_id}</b> - {rule_key} back to normal"
    try:
        asyncio.create_task(send_telegram_message(text))
    except RuntimeError:
        pass

def notify_daily_summary(fired_count: int, resolved_count: int, active_count: int):
    """Daily summary at 20:00 server time: alerts today, resolved, active"""
    text = (
        f"📊 <b>HBK IT Monitoring - Daily Summary</b>\n"
        f"• Alerts Today: <b>{fired_count}</b>\n"
        f"• Resolved Today: <b>{resolved_count}</b>\n"
        f"• Active Alerts: <b>{active_count}</b>"
    )
    try:
        asyncio.create_task(send_telegram_message(text))
    except RuntimeError:
        pass
