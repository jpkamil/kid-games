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
    python3 build_voice.py && ./build.sh
"""
import base64, json, os, shutil, subprocess, sys, wave

TTS   = os.path.expanduser("~/.local/share/nina-tts")
PY_   = os.path.join(TTS, "venv/bin/python")
MODEL = os.path.join(TTS, "models")
OUT, TMP = "voice_clips.js", "voicebuild"

# voice model, pitch/formant factor applied afterwards, phoneme length (>1 = slower)
NARR = ('en_US-amy-medium', 1.00, 1.06)
CAST = {
  'mom':     ('en_US-amy-medium',          1.00, 1.06),
  'grandma': ('en_US-kristin-medium',      0.95, 1.16),   # slower and lower
  'dad':     ('en_US-ryan-high',           0.99, 1.04),
  'teacher': ('en_GB-jenny_dioco-medium',  1.00, 1.06),
  'theo':    ('en_US-ryan-high',           1.20, 1.00),   # pitched up into a boy
  'oliver':  ('en_US-ryan-high',           1.13, 1.02),
  'mia':     ('en_US-hfc_female-medium',   1.08, 1.04),
}
FOR_LINE = {
  'mom':'Flowers for Mommy!', 'dad':'Flowers for Daddy!', 'grandma':'Flowers for Grandma!',
  'teacher':'Flowers for your teacher!', 'theo':'Flowers for Theo!',
  'oliver':'Flowers for Oliver!', 'mia':'Flowers for your friend Mia!',
}
THANKS = {
  'mom':'Thank you Nina! I love them!',
  'dad':'Wow, thank you Nina!',
  'grandma':'Oh Nina, they are beautiful. Thank you!',
  'teacher':'Thank you Nina! What lovely flowers.',
  'theo':'Thanks Nina! These are so pretty.',
  'oliver':'Thank you Nina! I love flowers.',
  'mia':'Thank you Nina! You are the best.',
}
WORDS  = ['NINA','CAT','DOG','MOM','DAD','SUN','THEO','BUS','OLIVER']
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

# ---- synthesise, grouped by model so each one loads exactly once ----
shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
jobs = {}
for cid,(text,model,pitch,length) in clips.items():
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

out, total = {}, 0
for cid,(text,model,pitch,length) in clips.items():
    wav = os.path.join(TMP, cid+'.wav'); m4a = os.path.join(TMP, cid+'.m4a')
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',wav,'-af',chain(pitch),
                    '-ar','22050','-ac','1','-c:a','aac','-b:a','32k', m4a], check=True)
    raw = open(m4a,'rb').read(); total += len(raw)
    out[cid] = base64.b64encode(raw).decode('ascii')

with open(OUT,'w') as f:
    f.write("/* Spoken lines rendered offline with Piper neural TTS (see build_voice.py).\n"
            "   Baked in so every device says it the same way, with no network. */\n")
    f.write("var VOICE_CLIPS = " + json.dumps(out, separators=(',',':')) + ";\n")
print("clips: %d   audio: %.0f KB   base64: %.0f KB"
      % (len(out), total/1024, os.path.getsize(OUT)/1024))
