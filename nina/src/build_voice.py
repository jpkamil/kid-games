#!/usr/bin/env python3
"""Bake every spoken line into the game as embedded AAC clips.

Browser speech synthesis on iOS is robotic and differs by device, so the fixed
vocabulary is rendered once here and shipped inside the HTML.

Rendered with Piper, a small offline neural TTS.  The first version of this
used macOS `say`, but every English voice on a stock Mac is compact,
super-compact or eloquence -- all formant/concatenative engines that sound
unmistakably robotic, which is exactly what Jeremy heard.  Piper is a neural
model, runs entirely offline, and needs nothing installed system-wide.

Setup (once):
    ./setup_voice.sh          # venv + models under ~/.local/share/nina-tts

Then:
    python3 build_voice.py && ./build.sh      # renders only lines not yet in voice_clips.js
    python3 build_voice.py --all              # re-render everything (changes every clip)
    python3 build_voice.py --redo=thx_dad,bye_dad   # re-render just those ids (a recast or a rewritten line)
"""
import base64, io, json, os, shutil, subprocess, sys, wave

TTS   = os.path.expanduser("~/.local/share/nina-tts")
PY_   = os.path.join(TTS, "venv/bin/python")
MODEL = os.path.join(TTS, "models")
OUT, TMP = "voice_clips.js", "voicebuild"

# voice model, pitch/formant factor applied afterwards, phoneme length (>1 = slower)
NARR = ('en_US-amy-medium', 1.00, 1.06)
# Auditioned with Jeremy 2026-09-03. Pitching a man's voice up by a fifth made
# the boys sound like chipmunks and the lowered, slowed Grandma sounded ominous;
# small shifts of the right base voice read as people.
CAST = {
  'mom':     ('en_US-amy-medium',          1.00, 1.06),
  'grandma': ('en_US-kristin-medium',      1.00, 1.06),
  'dad':     ('en_US-hfc_male-medium',     1.00, 1.04),   # warm, gentle, masculine
  'teacher': ('en_GB-jenny_dioco-medium',  1.00, 1.06),
  'charlotte': ('en_US-hfc_female-medium', 1.02, 1.02),  # Nina's big sister, 15
  'theo':    ('en_US-kathleen-low',        1.04, 0.98),
  'oliver':  ('en_US-hfc_male-medium',     1.10, 1.00),   # Daddy's voice, a tenth up
  'mia':     ('en_GB-alba-medium',         1.06, 1.00),
}
FOR_LINE = {
  'mom':'Flowers for Mommy!', 'dad':'Flowers for Daddy!', 'grandma':'Flowers for Grandma!',
  'teacher':'Flowers for your teacher!', 'charlotte':'Flowers for Charlotte!', 'theo':'Flowers for Theo!',
  'oliver':'Flowers for Oliver!', 'mia':'Flowers for your friend Mia!',
}
THANKS = {
  'mom':'Thank you Nina! I love them!',
  'dad':'Wow, thank you Nina!',
  'grandma':'Oh Nina, they are beautiful. Thank you!',
  'teacher':'Thank you Nina! What lovely flowers.',
  'charlotte':"Aww, thank you Nina! You're the best little sister.",
  'theo':'Thanks Nina! These are so pretty.',
  'oliver':'Thank you Nina! I love flowers.',
  'mia':'Thank you Nina! You are the best.',
}
WORDS  = ['NINA','CAT','DOG','MOM','DAD','SUN','CAR','THEO','BUS','BEE','PIG','OLIVER','HAT']
COLORS = ['pink','yellow','purple','red','blue','orange','white']
NUMS   = ['One!','Two!','Three!','Four!','Five!','Six!']

clips = {}
def add(cid, text, who=None, slow=None):
    model, pitch, length = CAST[who] if who else NARR
    clips[cid] = (text, model, pitch, length if slow is None else slow)

add('hi',     "Hi Nina! Let's go pick flowers!")
add('basket', "Your basket is full! Great job, Nina!")
add('water',  "Let's water the garden!")
add('find',   "Now find the letter")
add('g_again',  "Your garden is growing! Let's water it again.")
add('g_sprout', "Look! Little green sprouts came up!")
add('g_bud',    "Look, they got bigger! The buds are almost ready.")
for i,n in enumerate(NUMS): add('n%d'%(i+1), n, slow=1.22)
for c in COLORS:            add('c_'+c, "A %s flower!"%c)
for k,v in FOR_LINE.items(): add('for_'+k, v)
for k,v in THANKS.items():   add('thx_'+k, v, who=k)
for w in WORDS:
    add('sp_'+w, "Let's spell %s!"%w.lower())
    add('dn_'+w, "%s! You spelled %s!"%(w.lower(), w.lower()))
for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    add('L_'+ch, ch+".", slow=1.30)
for i,l in enumerate(["Great job!","Wonderful!","You did it!","Yay Nina!"]):
    add('yay%d'%i, l)
# the goats round
add('goats2',     "Oh no! Naughty goats took the flowers!")
add('g_feed',     "Munchy is hungry. Give her an apple or a pear!")
add('g_pet',      "Fluffy wants a cuddle. Pet her softly with your finger.")
add('g_climb',    "Peak is a mountain goat! Tap her, and she will climb the rock and pick the flower for you.")
add('f_apple',    "An apple!")
add('f_pear',     "A pear!")
add('goats_done', "You got all the flowers back! Good job, Nina!")
# nap time: everyone says goodbye in their own voice, then the game sleeps
add('nap',  "Farewell Nina! It's our nap time now. Bye bye!")
add('nap2', "Night night, Nina. See you after nap time!")
BYES = {   # everyone is off to their own nap too
  'mom':     "Bye bye, Nina! It's nap time for everyone. I love you!",
  'dad':     "Bye bye, Nina! It's my nap time too. See you soon!",
  'grandma': "Goodbye, Nina. It's nap time for me too. Sleep well, my darling.",
  'teacher': "Bye Nina! It's our nap time too. Have a lovely nap.",
  'charlotte': "Bye Nina! I'm going for a nap too. See you later!",
  'theo':    "Bye Nina! Time for my nap!",
  'oliver':  "See you later, Nina! I'm going for a nap too.",
  'mia':     "Bye Nina! It's nap time! Night night!",
}
for k,v in BYES.items(): add('bye_'+k, v, who=k)

# ---- incremental: keep clips already shipped, render only the new lines ----
# Piper samples its noise, so re-rendering an existing line changes how it
# sounds.  Lines Jeremy has already heard and approved stay byte-identical
# unless --all is passed.
keep = {}
if '--all' not in sys.argv and os.path.exists(OUT):
    import re
    m = re.search(r'var VOICE_CLIPS = (\{.*\});', io.open(OUT, encoding='utf-8').read(), re.S)
    if m:
        old = json.loads(m.group(1))
        keep = {k:v for k,v in old.items() if k in clips}
for a in sys.argv[1:]:
    if a.startswith('--redo='):
        for rid in a[7:].split(','): keep.pop(rid, None)
todo = {k:v for k,v in clips.items() if k not in keep}
print("existing clips kept: %d   new lines to render: %d" % (len(keep), len(todo)))

# ---- synthesise, grouped by model so each one loads exactly once ----
shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
jobs = {}
for cid,(text,model,pitch,length) in todo.items():
    jobs.setdefault(model, []).append({'id':cid, 'text':text, 'length':length})

worker = os.path.join(TMP, "_synth.py")
open(worker,"w").write('''
import json, sys, wave
from piper import PiperVoice, SynthesisConfig
spec = json.load(open(sys.argv[1]))
voice = PiperVoice.load(spec["model"])
for j in spec["jobs"]:
    with wave.open(j["out"], "wb") as w:
        voice.synthesize_wav(j["text"], w, SynthesisConfig(length_scale=j["length"]))
print("ok", len(spec["jobs"]))
''')
for model, js in jobs.items():
    for j in js: j['out'] = os.path.join(TMP, j['id']+'.wav')
    spec = os.path.join(TMP, 'spec_%s.json'%model)
    json.dump({'model': os.path.join(MODEL, model+'.onnx'), 'jobs': js}, open(spec,'w'))
    subprocess.run([PY_, worker, spec], check=True, stdout=subprocess.DEVNULL)
    print("  %-30s %d clips" % (model, len(js)))

# ---- trim, pitch, level, encode ----
TRIM = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02,"
        "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02,areverse")
# neural output needs almost nothing: a high-pass and a level match.  The heavy
# de-buzz EQ the `say` version used would only muddy it.
POST = "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11"

def chain(p):
    pitch = "" if abs(p-1.0) < 0.005 else \
        "aresample=22050,asetrate=%d,aresample=22050,atempo=%.4f," % (int(22050*p), 1.0/p)
    return pitch + TRIM + "," + POST

out, total = dict(keep), 0
for cid,(text,model,pitch,length) in todo.items():
    wav = os.path.join(TMP, cid+'.wav'); m4a = os.path.join(TMP, cid+'.m4a')
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',wav,'-af',chain(pitch),
                    '-ar','22050','-ac','1','-c:a','aac','-b:a','32k', m4a], check=True)
    raw = open(m4a,'rb').read(); total += len(raw)
    out[cid] = base64.b64encode(raw).decode('ascii')

out = {k: out[k] for k in clips if k in out}
with open(OUT,'w') as f:
    f.write("/* Spoken lines rendered offline with Piper neural TTS (see build_voice.py).\n"
            "   Baked in so every device says it the same way, with no network. */\n")
    f.write("var VOICE_CLIPS = " + json.dumps(out, separators=(',',':')) + ";\n")
print("clips: %d   audio: %.0f KB   base64: %.0f KB"
      % (len(out), total/1024, os.path.getsize(OUT)/1024))
