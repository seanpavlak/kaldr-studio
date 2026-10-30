#!/usr/bin/env python3
"""Beep speech: turn a string into chiptune babble.

Every letter becomes a short pulse-wave blip with a random pitch around the voice's base.
Vowels (and the vowel each consonant leans into) give the blip a formant "colour",
consonants add a noise click or hiss. No voice samples are used.

Usage:
  python beep_speech/beep_speech.py "Hello there! How are you?" -o hello.wav
  python beep_speech/beep_speech.py "Hi!" --pitch 420 --speed 20 -o hi.ogg
  python beep_speech/beep_speech.py --letters beep_speech/letters   # a.wav ... z.wav for runtime playback

From Python:
  from beep_speech import speak
  audio = speak("Hello!", pitch=300)   # float32 mono numpy array at 44.1 kHz
"""
import argparse
import re
import zlib
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, iirpeak, lfilter

SR = 44100

FORMANTS = {  # (F1, F2) in Hz
    "a": (800, 1250), "e": (500, 1850), "i": (330, 2300), "o": (520, 900), "u": (360, 800),
}
VOWELS = set(FORMANTS)
PLOSIVES = set("bdgkptqcx")
FRICATIVES = set("fhsvzj")
HIGH_NOISE = set("sztckx")  # brighter consonant noise
PAUSES = {" ": 0.9, "-": 0.9, ",": 2.5, ";": 2.5, ":": 2.5, ".": 4.0, "!": 4.0, "?": 4.0, "\n": 4.0}


def poly_blep(t, dt):
    """Band-limited step correction: rounds off the square wave's corners so it doesn't fizz."""
    out = np.zeros_like(t)
    a = t < dt
    x = t[a] / dt[a]
    out[a] = 2 * x - x * x - 1
    b = t > 1 - dt
    x = (t[b] - 1) / dt[b]
    out[b] = x * x + 2 * x + 1
    return out


def pulse(freqs, duty):
    """Band-limited pulse wave; `freqs` holds the frequency of every sample."""
    dt = freqs / SR
    phase = np.cumsum(dt) % 1.0
    return np.where(phase < duty, 1.0, -1.0) + poly_blep(phase, dt) - poly_blep((phase - duty) % 1.0, dt)


def lfsr_noise(n, rate, rng):
    """15-bit shift-register noise played back at `rate` Hz."""
    reg, bits = int(rng.integers(1, 0x7FFF)), np.empty(4096)
    for i in range(len(bits)):
        bit = (reg ^ (reg >> 1)) & 1
        reg = (reg >> 1) | (bit << 14)
        bits[i] = 1.0 - 2.0 * (reg & 1)
    return bits[(np.arange(n) * rate / SR).astype(int) % len(bits)]


def envelope(n, attack=0.004, release=0.025):
    env = np.ones(n)
    a, r = min(int(attack * SR), n), min(int(release * SR), n)
    env[:a] = np.linspace(0, 1, a)
    env[n - r:] *= np.linspace(1, 0, r)
    return env


def vowel_for(word: str, i: int) -> str:
    """Vowel colour for letter i: itself if a vowel, else the next vowel in the word."""
    for ch in word[i:] + word[:i][::-1]:
        if ch in VOWELS:
            return ch
    return "i" if "y" in word else "a"


def blip(letter: str, vowel: str, freq: float, dur: float, rng, drop: float = 1.0, width: float = 0.5) -> np.ndarray:
    n = max(int(dur * SR), 1)
    glide = freq * np.linspace(1 + 0.04 * drop, 1 - 0.03 * drop, n)  # slight downward chirp
    duty = width if letter in VOWELS else width * 0.5
    tone = pulse(glide, float(np.clip(duty, 0.05, 0.95)))

    f1, f2 = FORMANTS[vowel]
    if letter in "mnlrwy":  # softer, darker consonants
        f2 *= 0.75
    voiced = 0.35 * tone
    for f, gain in ((f1, 1.0), (f2, 0.7)):
        b, a = iirpeak(f, 6.0, fs=SR)
        voiced += gain * lfilter(b, a, tone)
    voiced /= np.abs(voiced).max() + 1e-9

    if letter in PLOSIVES:
        k = int(0.012 * SR)
        voiced[:k] = 0.6 * lfsr_noise(k, 16000 if letter in HIGH_NOISE else 5000, rng) * np.linspace(1, 0.3, k)
    elif letter in FRICATIVES:
        k = int(0.45 * n)
        hiss = 0.45 * lfsr_noise(k, 20000 if letter in HIGH_NOISE else 9000, rng)
        voiced[:k] = hiss * np.linspace(1, 0.5, k) + voiced[:k] * np.linspace(0, 1, k)
    return voiced * envelope(n)


def speak(text: str, pitch: float = 300.0, speed: float = 16.0, variation: float = 3.0,
          seed: int | None = None, *, length: float = 1.0, drop: float = 1.0,
          pauses: float = 1.0, brightness: float = 6000.0, lift: float = 1.0,
          width: float = 0.5) -> np.ndarray:
    """Render `text` as beep speech.

    pitch:      base voice pitch in Hz (low ~150 for gruff, ~450 for squeaky)
    speed:      letters per second
    variation:  random pitch spread in semitones
    seed:       for repeatable output; defaults to a hash of the text so the same line
                always sounds the same
    length:     how long each letter rings, relative to the usual blip
    drop:       downward swoop on each letter; 0 is flat, 1 is the usual chirp
    pauses:     how long spaces and punctuation wait
    brightness: low-pass cutoff in Hz
    lift:       how far ? and ! climb at the end of a sentence
    width:      pulse width of a vowel; consonants use half of it
    """
    rng = np.random.default_rng(zlib.crc32(text.encode()) if seed is None else seed)
    text = text.lower()
    hop = int(SR / speed)

    # each letter's word, and how far it is from the end of its sentence (for ?/! lilt)
    word_of = {}
    for m in re.finditer(r"[a-z]+", text):
        for i in range(m.start(), m.end()):
            word_of[i] = (m.group(), i - m.start())
    ending, left = [""] * len(text), [0] * len(text)
    end, count = "", 0
    for i in range(len(text) - 1, -1, -1):
        if text[i] in ".!?\n":
            end, count = text[i], 0
        elif text[i] in word_of:
            count += 1
        ending[i], left[i] = end, count

    events, pos = [], 0
    for i, ch in enumerate(text):
        if ch in PAUSES:
            pos += int(PAUSES[ch] * hop * pauses)
        elif i in word_of:
            semis = rng.uniform(-variation, variation)
            if ending[i] == "?" and left[i] <= 3:
                semis += 3.0 * (4 - left[i]) * lift  # questions rise at the end
            elif ending[i] == "!" and left[i] <= 3:
                semis += 2.0 * lift
            word, k = word_of[i]
            events.append((pos, blip(ch, vowel_for(word, k), pitch * 2 ** (semis / 12), 1.15 * length / speed, rng, drop, width)))
            pos += hop  # blips overlap slightly

    if not events:
        return np.zeros(1, dtype=np.float32)
    out = np.zeros(max(p + len(b) for p, b in events))
    for p, b in events:
        out[p:p + len(b)] += b
    out = lfilter(*butter(2, float(np.clip(brightness, 200, 16000)), btype="low", fs=SR), out)
    out = lfilter(*butter(1, 80, btype="high", fs=SR), out)
    return (out / (np.abs(out).max() + 1e-9) * 0.89).astype(np.float32)


def save(path: Path, audio: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".ogg":
        sf.write(path, audio, SR, format="OGG", subtype="VORBIS")
    else:
        sf.write(path, audio, SR, subtype="PCM_16")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("text", nargs="?", help="what to say")
    p.add_argument("-o", "--out", default="beep-speech.wav", help="output .wav or .ogg (default: beep-speech.wav)")
    p.add_argument("--pitch", type=float, default=300.0, help="base voice pitch in Hz (default 300)")
    p.add_argument("--speed", type=float, default=16.0, help="letters per second (default 16)")
    p.add_argument("--variation", type=float, default=3.0, help="random pitch spread in semitones (default 3)")
    p.add_argument("--length", type=float, default=1.0, help="letter length, 1 is the usual blip")
    p.add_argument("--drop", type=float, default=1.0, help="downward swoop, 0 is flat")
    p.add_argument("--pauses", type=float, default=1.0, help="space and punctuation wait, 1 is usual")
    p.add_argument("--brightness", type=float, default=6000.0, help="low-pass cutoff in Hz")
    p.add_argument("--lift", type=float, default=1.0, help="how far ? and ! climb")
    p.add_argument("--tone", type=float, default=0.5, help="vowel pulse width, 0.5 is the usual square")
    p.add_argument("--seed", type=int, help="random seed (default: derived from the text)")
    p.add_argument("--letters", metavar="DIR", help="instead, export one clip per letter a-z into DIR")
    args = p.parse_args()

    if args.letters:
        rng = np.random.default_rng(0)
        for ch in "abcdefghijklmnopqrstuvwxyz":
            audio = blip(ch, vowel_for(ch, 0), args.pitch, 1.15 * args.length / args.speed, rng, args.drop, args.tone)
            audio = lfilter(*butter(2, float(np.clip(args.brightness, 200, 16000)), btype="low", fs=SR), audio)
            save(Path(args.letters) / f"{ch}.wav", (audio / np.abs(audio).max() * 0.89).astype(np.float32))
        print(f"Wrote a.wav ... z.wav to {args.letters} (play them with random pitch shifts at runtime)")
        return
    if not args.text:
        p.error("give some text, or --letters DIR")
    audio = speak(
        args.text, args.pitch, args.speed, args.variation, args.seed,
        length=args.length, drop=args.drop, pauses=args.pauses,
        brightness=args.brightness, lift=args.lift, width=args.tone,
    )
    save(Path(args.out), audio)
    print(f"Wrote {args.out} ({len(audio) / SR:.2f}s)")


if __name__ == "__main__":
    main()
