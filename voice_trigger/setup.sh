#!/usr/bin/env bash
# Setup script for voice_trigger on Raspberry Pi + ReSpeaker
set -e

echo "=== Installing system dependencies ==="
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv portaudio19-dev

echo "=== Creating Python virtual environment ==="
python3 -m venv venv
source venv/bin/activate

echo "=== Installing Python packages ==="
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=== Downloading Vosk small English model ==="
MODEL_DIR="vosk-model-small-en-us-0.15"
if [ ! -d "$MODEL_DIR" ]; then
    wget -q --show-progress \
        https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip -q vosk-model-small-en-us-0.15.zip
    rm vosk-model-small-en-us-0.15.zip
    echo "Model downloaded to $MODEL_DIR/"
else
    echo "Model directory already exists – skipping download."
fi

echo ""
echo "=== Available audio input devices ==="
python3 - <<'EOF'
import pyaudio
pa = pyaudio.PyAudio()
for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"  [{i}] {info['name']}")
pa.terminate()
EOF

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit config.json and set your Telegram bot token + chat_id"
echo "  2. Confirm 'audio_device' in config.json matches your ReSpeaker name above"
echo "  3. Run: source venv/bin/activate && python voice_trigger.py"
