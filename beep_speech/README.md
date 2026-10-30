# Beep speech

Turns a string into chiptune babble. Every letter is a short synthesized
pulse-wave blip (no voice samples): vowels set the blip's tone colour, consonants add a noise
click or hiss, pitch wobbles randomly around the voice's base, and questions rise at the end.
The same text always produces the same audio.

```sh
../.venv/bin/python beep_speech.py "Hey there! Want to buy something?" -o line.wav   # or .ogg
../.venv/bin/python beep_speech.py "Hmph." --pitch 160 --speed 13 -o gruff.ogg       # gruff character
../.venv/bin/python beep_speech.py "Yay!" --pitch 460 --speed 20 -o squeaky.wav      # squeaky character
../.venv/bin/python beep_speech.py --letters letters                                 # a.wav ... z.wav
```

| Option        | Default | Meaning                                  |
|---------------|---------|------------------------------------------|
| `--pitch`     | 300     | base voice pitch in Hz (150 gruff – 450 squeaky) |
| `--speed`     | 16      | letters per second                       |
| `--variation` | 3       | random pitch spread in semitones         |
| `--seed`      | text hash | change for a different take of the same line |

From Python: `from beep_speech import speak; audio = speak("Hello!", pitch=300)` returns a
float32 mono array at 44.1 kHz.

`letters/` holds one clip per letter for doing it live in a game engine: play a clip per
character of the dialogue as it types out, randomising pitch by a few semitones each time.
`examples/` has sample lines.
