#!/usr/bin/env python3
"""Bake every spoken line into the game as embedded AAC clips.

Browser speech synthesis on iOS is robotic and differs by device, so the fixed
vocabulary is rendered once here and shipped inside the HTML.

Two things fight the robot sound:
  * engine choice.  Every English voice on a stock Mac is `compact`,
    `super-compact` or `eloquence` (run tools/list_voices for proof).  Eloquence
    (Flo, Sandy, Grandma, Rocko, Reed, Eddy) is the harshest of the three, so the
    cast is built from the MacinTalk voices instead -- Samantha, Moira, Daniel,
    Karen -- and the children are those same voices pitched up.
  * post-processing.  A little warmth at 280 Hz, a cut in the nasal 2.9 kHz band
    where the buzz lives, gentle de-essing and a 22 ms early reflection.

The real fix is an Enhanced or Premium voice, which is a free download in
System Settings > Accessibility > Spoken Content > System Voice > Manage Voices.
Install one, pass its name as argv[1], and rerun -- no code change needed.
"""
import base64, json, os, subprocess, sys, shutil

NARRATOR = sys.argv[1] if len(sys.argv) > 1 else "Samantha"
RATE     = sys.argv[2] if len(sys.argv) > 2 else "162"
OUT, TMP = "voice_clips.js", "voicebuild"

# voice, pitch-baseline markup, post pitch/formant factor
NARR  = (NARRATOR, 54, 1.00)
CAST = {
  'mom':     (NARRATOR,   54, 1.00),
  'grandma': ('Moira',    46, 0.97),   # warm, older; Eloquence "Grandma" is far harsher
  'dad':     ('Daniel',   40, 0.97),
  'teacher': ('Karen',    52, 1.00),
  'theo':    ('Daniel',   58, 1.14),   # pitched up into a boy
  'oliver':  ('Daniel',   66, 1.09),
  'mia':     ('Karen',    64, 1.10),
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
def add(cid, text, who=None, rate=None, pitch=None):
    v, pbas, p = CAST[who] if who else NARR
    clips[cid] = (text, v, rate or RATE, pbas if pitch is None else pitch, p)

add('hi',     "Hi Nina! Let's go pick flowers!")
add('basket', "Your basket is full! Great job Nina!")
add('water',  "Let's water the garden!")
add('find',   "Now find the letter")
# the garden is revisited, so it needs lines for each stage of growth
add('g_again',  "Your garden is growing! Let's water it again.")
add('g_sprout', "Look! Little green sprouts came up!")
add('g_bud',    "Look, they got bigger! The buds are almost ready.")
for i,n in enumerate(NUMS): add('n%d'%(i+1), n, rate='150')
for c in COLORS:            add('c_'+c, "A %s flower!"%c)
for k,v in FOR_LINE.items(): add('for_'+k, v)
for k,v in THANKS.items():   add('thx_'+k, v, who=k)
for w in WORDS:
    add('sp_'+w, "Let's spell %s!"%w.lower())
    add('dn_'+w, "%s! You spelled %s!"%(w.lower(), w.lower()))
for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    add('L_'+ch, ch+"!", rate='140')
for i,l in enumerate(["Great job!","Wonderful!","You did it!","Yay Nina!"]):
    add('yay%d'%i, l)

TRIM  = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,"
         "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,areverse")
WARM  = ("highpass=f=90,"
         "equalizer=f=280:t=q:w=1.0:g=2.5,"     # body
         "equalizer=f=2900:t=q:w=1.4:g=-3.5,"   # the nasal buzz that reads as "robot"
         "equalizer=f=5400:t=q:w=1.6:g=-2.0,"
         "lowpass=f=9000,deesser,"
         "aecho=0.9:0.25:22:0.08,"              # one early reflection: a room, not a reverb
         "loudnorm=I=-16:TP=-1.5:LRA=11")

def chain(p):
    pitch = "" if abs(p-1.0) < 0.005 else \
        "aresample=22050,asetrate=%d,aresample=22050,atempo=%.4f," % (int(22050*p), 1.0/p)
    return pitch + TRIM + "," + WARM

shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
out, total = {}, 0
for cid,(text,voice,rate,pbas,pitch) in clips.items():
    aiff = os.path.join(TMP, cid+'.aiff'); m4a = os.path.join(TMP, cid+'.m4a')
    subprocess.run(['say','-v',voice,'-r',rate,'-o',aiff,'[[pbas %d]] %s'%(pbas,text)], check=True)
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',aiff,'-af',chain(pitch),
                    '-ar','22050','-ac','1','-c:a','aac','-b:a','32k', m4a], check=True)
    raw = open(m4a,'rb').read(); total += len(raw)
    out[cid] = base64.b64encode(raw).decode('ascii')

with open(OUT,'w') as f:
    f.write("/* Spoken lines rendered offline with macOS `say` (narrator: %s),\n"
            "   warmed and pitched by build_voice.py.  Baked in so every device\n"
            "   says it the same way, with no network. */\n" % NARRATOR)
    f.write("var VOICE_CLIPS = " + json.dumps(out, separators=(',',':')) + ";\n")
print("clips: %d   audio: %.0f KB   base64: %.0f KB"
      % (len(out), total/1024, os.path.getsize(OUT)/1024))
