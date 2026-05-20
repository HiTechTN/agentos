import json
from typing import Any

import httpx

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger("notifications")


class NotificationManager:
    def __init__(self):
        self.settings = get_settings()

    async def send(self, channel: str, title: str, message: str, details: dict | None = None) -> bool:
        channel_map = {
            "slack": self._send_slack,
            "discord": self._send_discord,
            "console": self._send_console,
        }
        handler = channel_map.get(channel)
        if not handler:
            logger.log_warn("notifications", "unknown_channel", f"Unknown channel: {channel}")
            return False

        try:
            await handler(title, message, details)
            logger.log_action("notifications", f"sent_{channel}", "completed", details={"title": title})
            return True
        except Exception as e:
            logger.log_warn("notifications", f"{channel}_failed", str(e))
            return False

    async def notify_all(self, title: str, message: str, details: dict | None = None):
        channels = ["console"]
        if self.settings.slack_webhook_url:
            channels.append("slack")
        for ch in channels:
            await self.send(ch, title, message, details)

    async def _send_slack(self, title: str, message: str, details: dict | None = None):
        if not self.settings.slack_webhook_url:
            return
        payload = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": title}},
                {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            ]
        }
        if details:
            payload["blocks"].append({
                "type": "section",
                "fields": [{"type": "mrkdwn", "text": f"*{k}*: {v}"} for k, v in details.items()],
            })
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(self.settings.slack_webhook_url, json=payload)
            resp.raise_for_status()

    async def _send_discord(self, title: str, message: str, details: dict | None = None):
        if not self.settings.discord_webhook_url:
            return
        embed = {"title": title, "description": message, "color": 0x4c6ef5}
        if details:
            embed["fields"] = [{"name": k, "value": str(v), "inline": True} for k, v in details.items()]
        payload = {"embeds": [embed]}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(self.settings.discord_webhook_url, json=payload)
            resp.raise_for_status()

    async def _send_console(self, title: str, message: str, details: dict | None = None):
        logger.log_action("notification", title, "info", details={"message": message, **(details or {})})


_notification_manager: NotificationManager | None = None


def get_notifications() -> NotificationManager:
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
