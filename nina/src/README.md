# Nina's Flower Garden — build inputs

`../index.html` is generated. Do not hand-edit it.

    game.src.html   the game (references voice_clips.js)
    voice_clips.js  90 spoken lines, Piper neural TTS -> AAC -> base64
    build_voice.py  renders voice_clips.js (incremental: only lines not yet in the file)
    setup_voice.sh  one-time: venv + Piper models under ~/.local/share/nina-tts
    build.sh        inlines the clips into ../index.html

Adding a spoken line (a new word in WORDS, a new person, a new prompt):

    # edit the line tables at the top of build_voice.py AND the matching table in game.src.html
    python3 build_voice.py && ./build.sh

Only the new lines are synthesised. Piper samples noise, so re-rendering an
existing line changes how it sounds; the clips already shipped stay byte-identical.
To re-render everything (a different voice, a different speed):

    python3 build_voice.py --all && ./build.sh

Screenshots and scripted playtests without a phone: ~/.claude/skills/kid-web-games/scripts/wk_shot.swift
(swiftc -O wk_shot.swift -o wk_shot; ./wk_shot game.src.html setup.js out.png). Set
window.__fbDrive=true and call frame(ts) yourself for a deterministic clock.
