#!/usr/bin/env python3
"""Bake every spoken line into the game as embedded AAC clips.

Browser speech synthesis on iOS is robotic and inconsistent between devices.
The vocabulary here is small and fixed, so we render it once with macOS `say`
and ship the audio inside the HTML.  Same voice on every phone, works offline.
"""
import base64, json, os, subprocess, sys, shutil

NARRATOR = sys.argv[1] if len(sys.argv) > 1 else "Samantha"
RATE     = sys.argv[2] if len(sys.argv) > 2 else "165"
OUT      = "voice_clips.js"
TMP      = "voicebuild"

# each recipient answers in their own voice
CHAR_VOICE = {
  'mom':     NARRATOR,
  'dad':     'Reed (English (US))',
  'grandma': 'Grandma (English (US))',
  'teacher': 'Sandy (English (US))',
  'theo':    'Rocko (English (US))',
  'oliver':  'Eddy (English (US))',
  'mia':     'Flo (English (US))',
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

clips = {}   # id -> (text, voice, rate)
def add(cid, text, voice=None, rate=None):
    clips[cid] = (text, voice or NARRATOR, rate or RATE)

add('hi',        "Hi Nina! Let's go pick flowers!")
add('basket',    "Your basket is full! Great job Nina!")
add('water',     "Let's water the garden!")
add('find',      "Now find the letter")
for i,n in enumerate(NUMS): add('n%d'%(i+1), n, rate='150')
for c in COLORS:            add('c_'+c, "A %s flower!"%c)
for k,v in FOR_LINE.items():   add('for_'+k, v)
for k,v in THANKS.items():     add('thx_'+k, v, voice=CHAR_VOICE[k])
for w in WORDS:
    add('sp_'+w, "Let's spell %s!"%w.lower())
    add('dn_'+w, "%s! You spelled %s!"%(w.lower(), w.lower()))
for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    add('L_'+ch, ch+"!", rate='140')
for i,l in enumerate(["Great job!","Wonderful!","You did it!","Yay Nina!"]):
    add('yay%d'%i, l)

shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
out, total_raw = {}, 0
for cid,(text,voice,rate) in clips.items():
    aiff = os.path.join(TMP, cid+'.aiff'); m4a = os.path.join(TMP, cid+'.m4a')
    subprocess.run(['say','-v',voice,'-r',rate,'-o',aiff,text], check=True)
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',aiff,
                    '-af','silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,'
                          'areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,areverse,'
                          'loudnorm=I=-16:TP=-1.5:LRA=11',
                    '-ar','22050','-ac','1','-c:a','aac','-b:a','32k', m4a], check=True)
    raw = open(m4a,'rb').read(); total_raw += len(raw)
    out[cid] = base64.b64encode(raw).decode('ascii')

with open(OUT,'w') as f:
    f.write("/* Spoken lines, rendered offline with macOS `say` (voice: %s).\n"
            "   Baked in so every device says it the same way, with no network. */\n" % NARRATOR)
    f.write("var VOICE_CLIPS = ")
    f.write(json.dumps(out, separators=(',',':')))
    f.write(";\n")
print("clips: %d   audio: %.0f KB   base64: %.0f KB"
      % (len(out), total_raw/1024, os.path.getsize(OUT)/1024))
