"""
Action handlers for voice_trigger.py

Each action receives:
  config (dict)  – the full loaded config.json
  **kwargs       – any extra keys from the trigger entry in config.json
                   e.g. "message" for send_telegram

To add a new action:
  1. Define a function here: def my_action(config, **kwargs): ...
  2. Register it in the ACTION_REGISTRY dict in voice_trigger.py
  3. Add a trigger entry in config.json using the action name
"""

import logging
import requests

log = logging.getLogger(__name__)


def send_telegram(config: dict, message: str = "Voice trigger fired!", **kwargs) -> None:
    """Send *message* to the configured Telegram chat."""
    tg = config.get("telegram", {})
    token = tg.get("token", "")
    chat_id = tg.get("chat_id", "")

    if not token or not chat_id:
        raise ValueError("telegram.token and telegram.chat_id must be set in config.json")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    log.info("Telegram message sent to chat %s: '%s'", chat_id, message)
