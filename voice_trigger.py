#!/usr/bin/env python3
"""
Voice Trigger for Raspberry Pi + ReSpeaker
Listens for trigger phrases and executes configured actions.
"""

import json
import logging
import os
import sys
from datetime import datetime

import pyaudio
import vosk

import actions

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

with open(CONFIG_FILE) as f:
    config = json.load(f)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_dir = config.get("log_dir", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"voice_trigger_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Action registry  –  add new action functions in actions.py and list them here
# ---------------------------------------------------------------------------

ACTION_REGISTRY = {
    "send_telegram": actions.send_telegram,
    # "play_sound":  actions.play_sound,   # example of a future action
}

# ---------------------------------------------------------------------------
# Audio constants
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
CHUNK_SIZE = 4000


def get_device_index(pa: pyaudio.PyAudio, device_name: str | None) -> int:
    """Return the index of the first input device whose name contains *device_name*.
    Falls back to the system default if nothing matches."""
    if device_name:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if device_name.lower() in info["name"].lower() and info["maxInputChannels"] > 0:
                log.info("Matched audio device [%d]: %s", i, info["name"])
                return i
        log.warning("Device '%s' not found – using system default", device_name)
    default = pa.get_default_input_device_info()
    log.info("Using default audio device [%d]: %s", default["index"], default["name"])
    return default["index"]


def build_triggers(cfg: dict) -> list[dict]:
    """Validate and build the list of active triggers from config."""
    triggers = []
    for entry in cfg.get("triggers", []):
        phrase = entry.get("phrase", "").strip().lower()
        action_name = entry.get("action", "")
        if not phrase:
            log.warning("Skipping trigger with empty phrase: %s", entry)
            continue
        if action_name not in ACTION_REGISTRY:
            log.warning("Unknown action '%s' for phrase '%s' – skipping", action_name, phrase)
            continue
        triggers.append({
            "phrase": phrase,
            "action": ACTION_REGISTRY[action_name],
            "params": {k: v for k, v in entry.items() if k not in ("phrase", "action")},
        })
        log.info("Registered trigger: '%s' -> %s", phrase, action_name)
    return triggers


def main() -> None:
    model_path = config.get("vosk_model_path", "vosk-model")
    if not os.path.exists(model_path):
        log.error(
            "Vosk model not found at '%s'. "
            "Download a small English model from https://alphacephei.com/vosk/models "
            "and extract it here.",
            model_path,
        )
        sys.exit(1)

    log.info("Loading Vosk model from '%s' ...", model_path)
    model = vosk.Model(model_path)
    recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)

    triggers = build_triggers(config)
    if not triggers:
        log.error("No valid triggers found in config.json – nothing to do.")
        sys.exit(1)

    pa = pyaudio.PyAudio()
    device_index = get_device_index(pa, config.get("audio_device"))

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=CHUNK_SIZE,
    )
    stream.start_stream()
    log.info("Listening for triggers: %s", [t["phrase"] for t in triggers])

    try:
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip().lower()
                if not text:
                    continue
                log.info("Heard: '%s'", text)
                for trigger in triggers:
                    if trigger["phrase"] in text:
                        log.info("Trigger matched: '%s'", trigger["phrase"])
                        try:
                            trigger["action"](config, **trigger["params"])
                            log.info("Action completed for trigger '%s'", trigger["phrase"])
                        except Exception as exc:
                            log.error(
                                "Action failed for trigger '%s': %s",
                                trigger["phrase"],
                                exc,
                                exc_info=True,
                            )
    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == "__main__":
    main()
