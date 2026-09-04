#!/bin/bash
# One-time setup for the neural voice build. Nothing is installed system-wide;
# everything lives under ~/.local/share/nina-tts and can be deleted freely.
set -e
D=~/.local/share/nina-tts
mkdir -p "$D/models" && cd "$D"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip -q install --upgrade pip
./venv/bin/pip -q install piper-tts
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main
for v in en/en_US/amy/medium/en_US-amy-medium \
         en/en_US/kristin/medium/en_US-kristin-medium \
         en/en_US/hfc_female/medium/en_US-hfc_female-medium \
         en/en_US/ryan/high/en_US-ryan-high \
         en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium \
         en/en_US/hfc_male/medium/en_US-hfc_male-medium \
         en/en_US/kathleen/low/en_US-kathleen-low \
         en/en_GB/alba/medium/en_GB-alba-medium \
         en/en_US/libritts_r/medium/en_US-libritts_r-medium; do
  f=$(basename "$v")
  [ -f "models/$f.onnx" ] && continue
  curl -sL -o "models/$f.onnx"      "$BASE/$v.onnx"
  curl -sL -o "models/$f.onnx.json" "$BASE/$v.onnx.json"
  echo "fetched $f"
done
echo "ready: $D"
