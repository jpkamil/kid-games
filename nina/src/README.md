# Nina's Flower Garden — build inputs

`../index.html` is generated. Do not hand-edit it.

    game.src.html   the game (references voice_clips.js)
    voice_clips.js  79 spoken lines, macOS `say` -> AAC -> base64
    build_voice.py  regenerates voice_clips.js
    build.sh        inlines the clips into ../index.html

To change the narrator's voice:

    python3 build_voice.py "Shelley (English (US))" 165
    ./build.sh && cp ../index.html ../index.html   # build.sh writes nina.html here

`say -v '?'` lists installed voices. Enhanced/Premium voices download from
System Settings > Accessibility > Spoken Content > System Voice > Manage Voices
and sound noticeably better than the compact ones.
