#!/bin/bash
# Inline the baked voice clips into one self-contained file.
set -e
cd "$(dirname "$0")"
python3 - <<'PY'
import io
src = io.open("game.src.html", encoding="utf-8").read()
clips = io.open("voice_clips.js", encoding="utf-8").read()
tag = '<script src="voice_clips.js"></script>'
assert src.count(tag) == 1
out = src.replace(tag, "<script>\n" + clips + "</script>")
io.open("../index.html","w",encoding="utf-8").write(out)
print("../index.html  %.0f KB" % (len(out.encode("utf-8"))/1024))
PY
