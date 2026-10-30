#!/usr/bin/env python3
"""Turn a song into a vocal-free, seamlessly looping retro track.

Pipeline:
  1. Separate the song into stems with Demucs (htdemucs). Vocal audio is never used;
     only the sung melody's pitches are kept, to be played on the lead.
  2. Transcribe the instrumental stems onto a 16th-note grid:
       bass stem   -> bass line
       vocals stem -> lead melody      (instrument line where nobody sings)
       other stem  -> chords
       drums stem  -> kick/snare/hat
  3. Pick the bar-aligned section whose end flows best back into its start, and
     re-synthesize only that section at a constant tempo. Note tails that run
     past the end are wrapped onto the start, so the loop point is sample-exact.

Usage:
  python retroloop/retroloop.py song.mp3
  python retroloop/retroloop.py "https://www.youtube.com/watch?v=..."
  python retroloop/retroloop.py song.mp3 --min-seconds 30 --max-seconds 60 --preview

Outputs <out>/<name>.wav and <name>.ogg (use these in-game; MP3 adds encoder
padding that breaks gapless looping).
"""
import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter, lfilter


class LoopError(Exception):
    """A problem the person can act on. The command line exits with this message."""


SR = 44100
HOP = 512
STEPS_PER_BEAT = 4
STEPS_PER_BAR = 16
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
YT_DLP = [sys.executable, "-m", "yt_dlp"]  # the venv copy; YouTube breaks old yt-dlp versions often


# ---------------------------------------------------------------- input / stems

def fetch(src: str, workdir: Path) -> Path:
    if not re.match(r"https?://", src):
        return Path(src)
    out = workdir / "download.%(ext)s"
    for _attempt in range(3):  # YouTube intermittently returns 403; a retry usually works
        if subprocess.run([*YT_DLP, "-x", "--audio-format", "mp3", "--no-playlist", "-o", str(out), src]).returncode == 0:
            break
    else:
        raise LoopError("Download failed after 3 attempts.")
    return workdir / "download.mp3"


def youtube_title(url: str) -> str:
    res = subprocess.run([*YT_DLP, "--no-playlist", "--print", "title", url], capture_output=True, text=True)
    return res.stdout.strip() or "youtube"


def load_audio(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).T.copy()


def separate(path: Path) -> dict:
    """Returns mono stems {drums, bass, other, vocals}, cached by file hash."""
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:16]
    cache = CACHE_DIR / f"{digest}.npz"
    if cache.exists():
        return dict(np.load(cache))

    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    audio = load_audio(path)
    model = get_model("htdemucs")
    model.eval()
    wav = torch.from_numpy(audio)
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std()
    wav = ((wav - mean) / std)[None]

    print("Separating stems with Demucs...")
    for device in (["mps"] if torch.backends.mps.is_available() else []) + ["cpu"]:
        try:
            with torch.no_grad():
                out = apply_model(model, wav, device=device, split=True, overlap=0.25, progress=True)[0]
            break
        except RuntimeError as e:
            print(f"  {device} failed ({e}); retrying on cpu")
    out = (out * std + mean).cpu().numpy()
    stems = {name: out[i].mean(0) for i, name in enumerate(model.sources)}

    CACHE_DIR.mkdir(exist_ok=True)
    np.savez(cache, **stems)
    return stems


# ------------------------------------------------------------------ transcription

def step_grid(instrumental: np.ndarray) -> np.ndarray:
    """Times of 16th-note boundaries, derived from tracked beats."""
    _, beats = librosa.beat.beat_track(y=instrumental, sr=SR, hop_length=HOP, units="time")
    if len(beats) < 16:
        raise LoopError("Could not find a steady beat in this track.")
    bounds = [np.linspace(a, b, STEPS_PER_BEAT, endpoint=False) for a, b in zip(beats[:-1], beats[1:])]
    return np.concatenate(bounds + [beats[-1:]])


def per_step(feat: np.ndarray, frame_times: np.ndarray, bounds: np.ndarray, fn=np.mean) -> np.ndarray:
    """Aggregate frame features (d, n_frames) into steps -> (n_steps, d)."""
    idx = np.searchsorted(frame_times, bounds)
    out = np.zeros((len(bounds) - 1, feat.shape[0]))
    for s in range(len(bounds) - 1):
        a, b = idx[s], max(idx[s + 1], idx[s] + 1)
        out[s] = fn(feat[:, a:b], axis=1)
    return out


def step_rms(y: np.ndarray, bounds: np.ndarray) -> np.ndarray:
    rms = librosa.feature.rms(y=y, hop_length=HOP)
    t = librosa.frames_to_time(np.arange(rms.shape[1]), sr=SR, hop_length=HOP)
    return per_step(rms, t, bounds)[:, 0]


def active_mask(y: np.ndarray, bounds: np.ndarray, floor_db=-20.0) -> np.ndarray:
    r = step_rms(y, bounds)
    return r > np.percentile(r, 90) * 10 ** (floor_db / 20)


def clean_notes(notes: np.ndarray, min_len=2) -> np.ndarray:
    """Median-filter a step note sequence (-1 = rest) and drop blips shorter than min_len."""
    notes = notes.copy()
    padded = np.pad(notes, 1, mode="edge")
    med = np.array([np.median(padded[i:i + 3]) for i in range(len(notes))]).round().astype(int)
    notes = np.where(np.isin(med, notes), med, notes)
    s = 0
    while s < len(notes):
        e = s
        while e < len(notes) and notes[e] == notes[s]:
            e += 1
        if e - s < min_len and s > 0:
            notes[s:e] = notes[s - 1]
        s = e
    return notes


def monophonic_notes(y: np.ndarray, bounds: np.ndarray, fmin: float, fmax: float, sr: int) -> np.ndarray:
    """pYIN pitch track -> one MIDI note per step (-1 = rest)."""
    y = librosa.resample(y, orig_sr=SR, target_sr=sr)
    hop = sr // 86
    f0, voiced, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, frame_length=1024 if sr < 16000 else 2048, hop_length=hop)
    midi = np.where(voiced, librosa.hz_to_midi(np.nan_to_num(f0, nan=1.0)), np.nan)
    t = librosa.frames_to_time(np.arange(len(midi)), sr=sr, hop_length=hop)

    def pick(m, axis):
        m = m[0]
        v = m[~np.isnan(m)]
        return np.array([np.median(v) if len(v) >= max(1, 0.4 * len(m)) else np.nan])

    notes = per_step(midi[None], t, bounds, fn=pick)[:, 0]
    notes = np.where(np.isnan(notes), -1, np.round(notes)).astype(int)
    return notes


def bass_line(bass: np.ndarray, bounds: np.ndarray) -> np.ndarray:
    notes = monophonic_notes(bass, bounds, fmin=38.0, fmax=330.0, sr=11025)
    notes[~active_mask(bass, bounds)] = -1
    notes = np.where(notes >= 0, fold(notes, 36, 59), -1)
    return clean_notes(notes)


def fold(notes: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Move notes by octaves into [lo, hi]."""
    notes = notes.copy()
    while (m := notes < lo).any():
        notes[m] += 12
    while (m := notes > hi).any():
        notes[m] -= 12
    return notes


def harmony(other: np.ndarray, bass: np.ndarray, bounds: np.ndarray, key=None):
    """Chord per step (tuple of MIDI notes, for the arpeggio) and an instrumental lead line."""
    t = librosa.frames_to_time(np.arange(1 + len(other) // HOP), sr=SR, hop_length=HOP)

    chroma = librosa.feature.chroma_cqt(y=other + 0.5 * bass, sr=SR, hop_length=HOP)
    chroma = per_step(chroma, t[: chroma.shape[1]], bounds)
    kernel = np.ones(STEPS_PER_BEAT) / STEPS_PER_BEAT  # chords move slower than notes
    chroma = np.apply_along_axis(lambda c: np.convolve(c, kernel, mode="same"), 0, chroma)

    active = active_mask(other, bounds)
    triads = diatonic_triads(key) if key is not None else []
    chords, prev = [], ()
    meter_chords = chords_by_half_bar(chroma, active, key) if key is not None else None
    for s, c in enumerate(chroma):
        if not active[s]:
            chords.append(())
            prev = ()
            continue
        if key is not None:
            # the key's own chord that best matches what's sounding
            def fit(tri, c=c):
                return sum(c[pc] for pc in tri[1]) - 0.35 * sum(c[pc] for pc in range(12) if pc not in tri[1]) / 9
            root, tri = max(triads, key=fit)
            notes = tuple(sorted(57 + (pc - 57) % 12 for pc in tri))  # voiced between A3 and G#4
            if prev and fit((0, tuple(n % 12 for n in prev))) >= 0.9 * fit((root, tri)):
                chords.append(prev)
                continue
            chords.append(notes)
            prev = notes
            continue
        top = [pc for pc in np.argsort(c)[::-1][:3] if c[pc] >= 0.6 * c.max()]
        # hysteresis: keep the previous chord unless the new one is clearly stronger
        if prev and sum(c[n % 12] for n in prev) >= 0.85 * sum(c[pc] for pc in top) * len(prev) / len(top):
            chords.append(prev)
            continue
        notes = tuple(sorted(60 + pc for pc in top))
        if len(notes) == 1:
            notes = (notes[0], notes[0] + 12)
        chords.append(notes)
        prev = notes

    # lead: strongest harmonic-salience pitch in the melody register
    cqt = np.abs(librosa.cqt(other, sr=SR, hop_length=HOP, fmin=librosa.midi_to_hz(36), n_bins=84))
    sal = cqt.copy()
    for shift, w in ((12, 0.5), (19, 0.33), (24, 0.25)):
        sal[:-shift] += w * cqt[shift:]
    sal = per_step(sal, t[: sal.shape[1]], bounds)
    band = sal[:, 55 - 36: 85 - 36]
    peak = band.argmax(1)
    confidence = band.max(1) / (band.mean(1) + 1e-9)
    lead = np.where(active & (confidence > np.percentile(confidence, 40)), peak + 55, -1)
    if meter_chords is not None:
        chords = meter_chords
    return chords, clean_notes(lead, min_len=2)


# ------------------------------------------------------------------ keeping it in key

# Krumhansl-Kessler key profiles (major, minor), for estimating the song's key.
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)
MINOR_STEPS = (0, 2, 3, 5, 7, 8, 10)


def estimate_key(chroma_total: np.ndarray):
    """(tonic pitch class, is_minor) that best fits the whole song's chroma."""
    best, key = -2.0, (0, False)
    for tonic in range(12):
        for minor, prof in ((False, KK_MAJOR), (True, KK_MINOR)):
            r = np.corrcoef(chroma_total, np.roll(prof, tonic))[0, 1]
            if r > best:
                best, key = r, (tonic, minor)
    return key


def scale_of(key) -> set:
    tonic, minor = key
    steps = MINOR_STEPS if minor else MAJOR_STEPS
    pcs = {(tonic + s) % 12 for s in steps}
    if minor:
        pcs.add((tonic + 11) % 12)  # the raised seventh: minor keys lean on a major V
    return pcs


def diatonic_triads(key):
    """The key's chords as (root pc, (pcs...)): its seven triads, plus V major in minor."""
    tonic, minor = key
    steps = MINOR_STEPS if minor else MAJOR_STEPS
    scale = [(tonic + s) % 12 for s in steps]
    triads = [(scale[i], (scale[i], scale[(i + 2) % 7], scale[(i + 4) % 7])) for i in range(7)]
    if minor:
        v = (tonic + 7) % 12
        triads.append((v, (v, (v + 4) % 12, (v + 7) % 12)))
    return triads


def snap_to_scale(notes: np.ndarray, scale: set) -> np.ndarray:
    """Move out-of-key notes a semitone to the nearest scale tone (rests stay rests)."""
    out = notes.copy()
    for i, m in enumerate(notes):
        if m < 0 or m % 12 in scale:
            continue
        down, up = m - 1, m + 1
        out[i] = down if down % 12 in scale else up if up % 12 in scale else m
    return out


def soften_clashes(lead: np.ndarray, chords: list) -> np.ndarray:
    """On the beat, a melody note a semitone (or tritone) off the chord moves to the
    nearest chord tone, so the tune and the harmony stop grinding."""
    out = lead.copy()
    for i, m in enumerate(lead):
        if m < 0 or i % STEPS_PER_BEAT or not chords[i]:
            continue
        pcs = {n % 12 for n in chords[i]}
        if m % 12 in pcs:
            continue
        grind = any((m - p) % 12 in (1, 11, 6) for p in pcs)
        if grind:
            out[i] = min((m + d for d in range(-2, 3) if (m + d) % 12 in pcs), key=lambda x: abs(x - m), default=m)
    return out


# ------------------------------------------------------------------ meter and voice leading
#
# Transcription changes its mind every sixteenth; music doesn't. These pass a
# steady harmonic rhythm and keep the parts agreeing with one another.

HALF_BAR = STEPS_PER_BAR // 2


def chords_by_half_bar(chroma: np.ndarray, active: np.ndarray, key) -> list:
    """One of the key's chords per half bar, chosen from the whole half bar."""
    triads = diatonic_triads(key)
    out, prev = [], None
    for h in range(0, len(chroma), HALF_BAR):
        window = chroma[h:h + HALF_BAR]
        on = active[h:h + HALF_BAR]
        if not on.any():
            out.extend([()] * len(window))
            prev = None
            continue
        c = window[on].sum(0)

        def fit(tri, c=c):
            return sum(c[pc] for pc in tri[1]) - 0.35 * sum(c[pc] for pc in range(12) if pc not in tri[1]) / 9

        best = max(triads, key=fit)
        # stay put unless the new chord is clearly better (smooth harmony)
        if prev is not None and fit(prev) >= 0.92 * fit(best):
            best = prev
        prev = best
        notes = tuple(sorted(57 + (pc - 57) % 12 for pc in best[1]))
        out.extend([notes] * len(window))
    return out


def quantize_melody(lead: np.ndarray) -> np.ndarray:
    """Eighth-note grid: each eighth takes its most common pitch; nothing shorter."""
    out = lead.copy()
    for i in range(0, len(lead), 2):
        pair = lead[i:i + 2]
        voiced = pair[pair >= 0]
        if len(voiced) == 0:
            out[i:i + 2] = -1
        else:
            vals, counts = np.unique(voiced, return_counts=True)
            out[i:i + 2] = vals[np.argmax(counts)]
    return out


def lead_follows_chords(lead: np.ndarray, chords: list, scale: set) -> np.ndarray:
    """Strong beats land on chord tones; weak eighths stay in key; nothing sits a
    semitone (or a tritone) off a sounding chord tone."""
    out = lead.copy()
    for i, m in enumerate(lead):
        if m < 0 or not chords[i]:
            continue
        pcs = {n % 12 for n in chords[i]}
        strong = i % STEPS_PER_BEAT == 0
        grind = any((m - p) % 12 in (1, 11, 6) for p in pcs)
        if (strong and m % 12 not in pcs) or grind:
            out[i] = min((m + d for d in range(-4, 5) if (m + d) % 12 in pcs), key=lambda x: abs(x - m), default=m)
        elif m % 12 not in scale:
            out[i] = min((m + d for d in range(-2, 3) if (m + d) % 12 in scale), key=lambda x: abs(x - m), default=m)
    return out


def bass_follows_chords(bass: np.ndarray, chords: list) -> np.ndarray:
    """A beat at a time: the root on each half bar's downbeat, otherwise the
    nearest chord tone to what was played."""
    out = bass.copy()
    for b in range(0, len(bass), STEPS_PER_BEAT):
        chord = chords[b]
        played = bass[b:b + STEPS_PER_BEAT]
        voiced = played[played >= 0]
        if not chord:
            continue
        pcs = [n % 12 for n in chord]
        root = pcs[0]
        anchor = int(np.median(voiced)) if len(voiced) else 43
        if b % HALF_BAR == 0 or not len(voiced):
            target = root
        else:
            target = min(pcs, key=lambda pc: min((anchor - pc) % 12, (pc - anchor) % 12))
        note = 36 + (target - 36) % 12
        if note + 12 <= 52 and abs(note + 12 - anchor) < abs(note - anchor):
            note += 12
        out[b:b + STEPS_PER_BEAT] = note
    return out


def vocal_melody(vocals: np.ndarray, bounds: np.ndarray) -> np.ndarray:
    notes = monophonic_notes(vocals, bounds, fmin=80.0, fmax=1000.0, sr=22050)
    notes[~active_mask(vocals, bounds, floor_db=-25)] = -1
    return clean_notes(np.where(notes >= 0, fold(notes, 60, 84), -1))


def drum_hits(drums: np.ndarray, bounds: np.ndarray) -> np.ndarray:
    """Per step: 0 none, 1 hat, 2 snare, 3 kick."""
    hits = np.zeros(len(bounds) - 1, dtype=int)
    onsets = librosa.onset.onset_detect(y=drums, sr=SR, hop_length=HOP, units="frames")
    if len(onsets) == 0:
        return hits
    spec = np.abs(librosa.stft(drums, n_fft=2048, hop_length=HOP)) ** 2
    freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
    bands = [(20, 150), (150, 3000), (5000, 16000)]
    energy = np.array([[spec[(freqs >= lo) & (freqs < hi), f:f + 4].sum() for lo, hi in bands] for f in onsets])
    z = np.log(energy + 1e-12)
    z = (z - z.mean(0)) / (z.std(0) + 1e-9)
    times = librosa.frames_to_time(onsets, sr=SR, hop_length=HOP)
    steps = np.clip(np.searchsorted(bounds, times - 0.5 * np.diff(bounds).mean()), 0, len(hits) - 1)
    for s, (low, mid, _high) in zip(steps, z):
        kind = 3 if low > 0.5 and low >= mid else 2 if mid > 0.3 else 1
        hits[s] = max(hits[s], kind)
    return hits


# ------------------------------------------------------------------ loop choice

def choose_loop(features: np.ndarray, step_sec: float, min_sec: float, max_sec: float, first_step: int = 0):
    """Find (start, end) steps, a whole number of bars apart, where the music after
    `end` most resembles the music after `start` (so jumping end->start is invisible)."""
    f = features / (np.linalg.norm(features, axis=1, keepdims=True) + 1e-9)
    sim = f @ f.T
    n = len(f)
    behind, ahead = STEPS_PER_BAR, 2 * STEPS_PER_BAR
    min_bars = max(2, int(np.ceil(min_sec / step_sec / STEPS_PER_BAR)))
    max_bars = max(min_bars, int(max_sec / step_sec / STEPS_PER_BAR))
    starts = np.arange(max(behind, first_step), n - ahead, STEPS_PER_BEAT)
    energy = np.linalg.norm(features, axis=1)
    loud = np.convolve(energy, np.ones(STEPS_PER_BAR), mode="same") > 0.5 * np.median(energy) * STEPS_PER_BAR

    best = []
    for bars in range(min_bars, max_bars + 1):
        length = bars * STEPS_PER_BAR
        i = starts[starts + length + ahead <= n]
        if len(i) == 0:
            break
        j = i + length
        score = np.mean([sim[i + k, j + k] for k in range(-behind, ahead)], axis=0)
        score[~loud[i]] = -1  # don't start in a quiet intro / break
        k = score.argmax()
        best.append((score[k], length, int(i[k]), int(j[k])))
    if not best:
        raise LoopError("Track is too short for the requested loop length.")
    top = max(b[0] for b in best)
    # among near-best candidates, prefer the longest loop
    score, _, start, end = max((b for b in best if b[0] >= top - 0.02), key=lambda b: b[1])
    return start, end, score


# ------------------------------------------------------------------ 8-bit synth

def gb_freq(midi, wave=False):
    """Snap a note to an 11-bit period so the pitch steps the way a cheap wave chip does."""
    f = 440.0 * 2 ** ((np.asarray(midi) - 69) / 12)
    clock = 65536 if wave else 131072
    x = np.clip(np.round(2048 - clock / f), 0, 2047)
    return clock / (2048 - x)


def envelope(n: int, vol: int, pace: float, floor: int = 0, attack=0.004, release=0.02) -> np.ndarray:
    """Stepped volume envelope (level drops by 1/15 every `pace` seconds), smoothed
    and given short fades in/out so notes don't click."""
    t = np.arange(n) / SR
    level = np.maximum(vol - t / pace if pace > 0 else np.full(n, float(vol)), floor) / 15.0
    if attack:
        level *= np.minimum(1.0, t / attack)
    r = min(int(release * SR), n)
    if r:
        level[-r:] *= np.linspace(1.0, 0.0, r)
    return level


def poly_blep(t, dt):
    """Band-limited step correction: rounds off a square wave's corners so it doesn't fizz."""
    out = np.zeros_like(t)
    a = t < dt
    x = t[a] / dt[a]
    out[a] = 2 * x - x * x - 1
    b = t > 1 - dt
    x = (t[b] - 1) / dt[b]
    out[b] = x * x + 2 * x + 1
    return out


def pulse(freqs, duty):
    """Band-limited pulse wave; `freqs` holds the frequency of every output sample."""
    dt = freqs / SR
    phase = np.cumsum(dt) % 1.0
    return np.where(phase < duty, 1.0, -1.0) + poly_blep(phase, dt) - poly_blep((phase - duty) % 1.0, dt)


def vibrato(freq, n, depth=0.004, rate=5.5, delay=0.18):
    """Gentle vibrato that fades in on held notes."""
    t = np.arange(n) / SR
    return freq * (1 + depth * np.clip((t - delay) / 0.2, 0, 1) * np.sin(2 * np.pi * rate * t))


WAVE_TABLE = np.linspace(-1, 1, 16).tolist() + np.linspace(1, -1, 16).tolist()
WAVE_TABLE = np.array(WAVE_TABLE)


def wave(freq, n):
    """Wave channel playback, interpolated between table entries to soften it."""
    pos = np.arange(n) * freq * 32 / SR
    i = pos.astype(int)
    frac = pos - i
    return WAVE_TABLE[i % 32] * (1 - frac) + WAVE_TABLE[(i + 1) % 32] * frac


def lfsr(width: int) -> np.ndarray:
    reg, out = 0x7FFF, []
    for _ in range((1 << width) - 1):
        bit = (reg ^ (reg >> 1)) & 1
        reg = (reg >> 1) | (bit << 14)
        if width == 7:
            reg = (reg & ~0x40) | (bit << 6)
        out.append(1.0 - 2.0 * (reg & 1))
    return np.array(out)


NOISE15 = lfsr(15)


def noise(rate, n):
    return NOISE15[(np.arange(n) * rate / SR).astype(int) % len(NOISE15)]


def note_runs(notes):
    """Group consecutive identical step values into (start_step, length, value)."""
    s = 0
    while s < len(notes):
        e = s + 1
        while e < len(notes) and notes[e] == notes[s]:
            e += 1
        yield s, e - s, notes[s]
        s = e


def fill_gaps(seq, is_rest, max_steps=None):
    """Hold the previous value through rests (wrapping around the loop) so parts don't drop out."""
    seq = list(seq)
    n = len(seq)
    held = [i for i in range(n) if not is_rest(seq[i])]
    if not held:
        return seq
    out, cur, gap = seq[:], None, 0
    for k in range(held[0], held[0] + n):
        i = k % n
        if not is_rest(seq[i]):
            cur, gap = seq[i], 0
        else:
            gap += 1
            if max_steps is None or gap <= max_steps:
                out[i] = cur
    return out


def circular(b, a, x):
    """Filter a loop as if it repeats forever, so the filter state matches at the seam."""
    n = x.shape[1]
    return lfilter(b, a, np.concatenate([x, x], axis=1), axis=1)[:, n:]


def _fold(stereo: np.ndarray, length: int, tail: int) -> np.ndarray:
    loop = stereo[:, :length].copy()
    loop[:, :tail] += stereo[:, length:length + tail]
    return loop


def _stem_mix(ch: dict, gains: dict, pans: dict, length: int, tail: int):
    """Pan and level each part, then fold note tails back onto the start.

    The parts are the same length as the mix and sum to it before the shared
    bus (room, echo, filters) is applied.
    """
    stems = {}
    mixed = np.zeros((2, length + tail))
    for name, sig in ch.items():
        stereo = np.zeros((2, length + tail))
        gain, pan = gains[name], pans[name]
        stereo[0] = sig * gain * (1 - max(pan, 0))
        stereo[1] = sig * gain * (1 + min(pan, 0))
        mixed += stereo
        stems[name] = _fold(stereo, length, tail)
    return _fold(mixed, length, tail), stems


def _deliver(mix: np.ndarray, stems: dict, polish) -> tuple[np.ndarray, dict]:
    """Run the shared bus on the mix and on every part, then one shared level.

    Because the bus is linear, the parts still add up to the finished loop.
    """
    mix = polish(mix)
    stems = {name: polish(sig) for name, sig in stems.items()}
    peak = float(np.abs(mix).max()) + 1e-9
    gain = 0.89 / peak
    return mix * gain, {name: sig * gain for name, sig in stems.items()}


def render(
    lead, chords, bass, hits, step_samples: int, classic: bool = False, *,
    space: float = 1.0, brightness: float = 1.0,
    lead_level: float = 1.0, chords_level: float = 1.0,
    bass_level: float = 1.0, drums_level: float = 1.0,
) -> tuple[np.ndarray, dict]:
    lead = fill_gaps(lead, lambda m: m < 0, max_steps=4)
    bass = fill_gaps(bass, lambda m: m < 0, max_steps=STEPS_PER_BAR // 2)
    chords = fill_gaps(chords, lambda c: not c)

    n_steps = len(bass)
    length = n_steps * step_samples
    tail = SR  # room for releases/drum tails; folded back onto the loop start
    ch = {k: np.zeros(length + tail) for k in ("lead", "arp", "bass", "noise")}

    def put(name, start, sig):
        ch[name][start:start + len(sig)] += sig

    for s, k, m in note_runs(lead):
        if m >= 0:
            n = k * step_samples
            put("lead", s * step_samples, pulse(vibrato(gb_freq(m), n), 0.5) * envelope(n, 12, 0.15, floor=8))

    # one arpeggio note per step reads as a figure; three per step jitters
    arp_len = max(1, step_samples // 3) if classic else step_samples
    for s, k, chord in note_runs(chords):
        if chord:
            n = k * step_samples
            seq = np.array(chord)[(np.arange(n) // arp_len) % len(chord)]
            put("arp", s * step_samples, pulse(gb_freq(seq), 0.25) * envelope(n, 8, 0.3, floor=5))

    for s, k, m in note_runs(bass):
        if m >= 0:
            n = k * step_samples
            put("bass", s * step_samples, wave(gb_freq(m, wave=True), n) * envelope(n, 15, 0, release=0.03))

    kick_n, snare_n, hat_n = int(0.10 * SR), int(0.16 * SR), int(0.05 * SR)
    drums = {
        1: noise(22000, hat_n) * envelope(hat_n, 6, 0.006, attack=0.001),
        2: noise(9000, snare_n) * envelope(snare_n, 12, 0.012, attack=0.001),
        3: pulse(np.geomspace(180, 40, kick_n), 0.5) * envelope(kick_n, 15, 0.007, attack=0.001),
    }
    for s, h in enumerate(hits):
        if h:
            put("noise", s * step_samples, drums[h])

    gains = {"lead": 0.20 * lead_level, "arp": 0.10 * chords_level, "bass": 0.30 * bass_level, "noise": 0.18 * drums_level}
    if not classic:
        gains = {"lead": 0.19 * lead_level, "arp": 0.08 * chords_level, "bass": 0.30 * bass_level, "noise": 0.11 * drums_level}
    pans = {"lead": 0.15, "arp": -0.35, "bass": 0.0, "noise": 0.05}
    loop, stems = _stem_mix(ch, gains, pans, length, tail)

    def polish(sig):
        # soft ping-pong echo (dotted 8th) to fill space; np.roll keeps it circular
        delay = 3 * step_samples
        wet = (0.22 if classic else 0.12) * space
        sig = sig + sum(wet * 0.45 ** (k - 1) * np.roll(sig[::(-1) ** k], k * delay, axis=1) for k in range(1, 5))
        # tame the top end, and block DC
        cutoff = float(np.clip((5000 if classic else 3800) * brightness, 400, 16000))
        sig = circular(*butter(2, cutoff, btype="low", fs=SR), sig)
        a = np.exp(-2 * np.pi * 25 / SR)
        return circular([a, -a], [1, -a], sig)

    return _deliver(loop, stems, polish)


# ------------------------------------------------------------------ soft style (16-bit-ish)
#
# Warmer instruments that still read as retro: a rounded lead, plucked strings
# for the arpeggio over a quiet pad, a round bass, gentle drums and a small
# room. Everything is built per note and summed, then the room and filters
# run circularly so the loop seam stays sample-exact.

def midi_hz(m):
    return 440.0 * 2 ** ((np.asarray(m, dtype=float) - 69) / 12)


def tri_osc(freq, n):
    ph = (np.arange(n) * freq / SR) % 1.0
    return 4 * np.abs(ph - 0.5) - 1


def adsr(n, a=0.012, d=0.12, s=0.7, r=0.06):
    t = np.arange(n) / SR
    env = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    rn = min(int(r * SR), n)
    if rn:
        env[-rn:] *= np.linspace(1, 0, rn) ** 1.5
    return env


def onepole_lp(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    return lfilter([1 - a], [1, -a], x)


_pluck_cache = {}


def pluck(m, n, bright=0.5):
    """Karplus-Strong string: a burst of soft noise through a tuned, damped delay line."""
    key = (int(m), n)
    if key in _pluck_cache:
        return _pluck_cache[key]
    f = float(midi_hz(m))
    d = max(2, int(round(SR / f)))
    rng = np.random.default_rng(int(m))
    burst = np.zeros(n)
    burst[:d] = onepole_lp(rng.uniform(-1, 1, d), 1800 + 2400 * bright)
    g = 0.993
    a = np.zeros(d + 2)
    a[0], a[d], a[d + 1] = 1.0, -g * 0.5, -g * 0.5
    y = lfilter([1.0], a, burst)
    y *= np.minimum(1.0, (n - np.arange(n)) / (0.04 * SR))  # release at the note's end
    _pluck_cache[key] = y
    return y


def soft_lead(m, n):
    f = vibrato(midi_hz(m), n, depth=0.005, rate=5.0, delay=0.22)
    ph = np.cumsum(f / SR) % 1.0
    tri = 4 * np.abs(ph - 0.5) - 1
    sine = np.sin(2 * np.pi * ph)
    ph2 = np.cumsum(f * 1.003 / SR) % 1.0  # a detuned twin for width
    tri2 = 4 * np.abs(ph2 - 0.5) - 1
    # flute-like: triangle and sine only, no square edge anywhere
    return (0.45 * tri + 0.35 * sine + 0.25 * tri2) * adsr(n, a=0.02, d=0.3, s=0.75, r=0.06)


def soft_pad(chord, n):
    out = np.zeros(n)
    for m in chord:
        f = float(midi_hz(m - 12))
        ph = (np.arange(n) * f / SR) % 1.0
        saw = 2 * ph - 1
        out += onepole_lp(saw, 900) * 0.6 + np.sin(2 * np.pi * ph) * 0.4
    return out / max(1, len(chord)) * adsr(n, a=0.25, d=0.6, s=0.8, r=0.2)


def soft_bass(m, n):
    f = float(midi_hz(m))
    t = np.arange(n) / SR
    body = 0.6 * tri_osc(f, n) + 0.4 * np.sin(2 * np.pi * f * t)
    return np.tanh(1.4 * body) * adsr(n, a=0.006, d=0.2, s=0.8, r=0.04)


def soft_drums():
    k_n, s_n, h_n = int(0.22 * SR), int(0.2 * SR), int(0.06 * SR)
    t = np.arange(k_n) / SR
    kick = np.sin(2 * np.pi * np.cumsum(np.geomspace(120, 42, k_n)) / SR) * np.exp(-t / 0.09)
    rng = np.random.default_rng(3)
    ts = np.arange(s_n) / SR
    snare = (onepole_lp(rng.uniform(-1, 1, s_n), 5000) * 0.7 + np.sin(2 * np.pi * 185 * ts) * 0.5) * np.exp(-ts / 0.06)
    th = np.arange(h_n) / SR
    hn = rng.uniform(-1, 1, h_n)
    hat = (hn - onepole_lp(hn, 6000)) * np.exp(-th / 0.015)
    return {1: hat * 0.35, 2: snare * 0.8, 3: kick}


def room(loop, mix=0.18):
    """A small SNES-ish room: parallel feedback combs into allpasses, run circularly."""
    wet = np.zeros_like(loop)
    for ch in range(2):
        x = loop[ch]
        acc = np.zeros_like(x)
        for ms in (29.7, 37.1, 41.1, 43.7):
            d = int(ms * SR / 1000) + ch * 7
            a = np.zeros(d + 1)
            a[0], a[d] = 1.0, -0.72
            acc += circular(np.array([1.0]), a, x[None])[0]
        for ms in (5.0, 1.7):
            d = int(ms * SR / 1000)
            b = np.zeros(d + 1)
            a = np.zeros(d + 1)
            b[0], b[d] = -0.6, 1.0
            a[0], a[d] = 1.0, -0.6
            acc = circular(b, a, acc[None])[0]
        wet[ch] = acc / 4
    wet = circular(*butter(1, 3500, btype="low", fs=SR), wet)
    return loop + mix * wet


def render_soft(
    lead, chords, bass, hits, step_samples: int, *,
    space: float = 1.0, brightness: float = 1.0,
    lead_level: float = 1.0, chords_level: float = 1.0,
    bass_level: float = 1.0, drums_level: float = 1.0,
) -> tuple[np.ndarray, dict]:
    lead = fill_gaps(lead, lambda m: m < 0, max_steps=4)
    bass = fill_gaps(bass, lambda m: m < 0, max_steps=STEPS_PER_BAR // 2)
    chords = fill_gaps(chords, lambda c: not c)

    n_steps = len(bass)
    length = n_steps * step_samples
    tail = SR
    ch = {k: np.zeros(length + tail) for k in ("lead", "pluck", "pad", "bass", "drums")}

    def put(name, start, sig):
        ch[name][start:start + len(sig)] += sig

    for s, k, m in note_runs(lead):
        if m >= 0:
            put("lead", s * step_samples, soft_lead(m, k * step_samples + int(0.04 * SR)))

    ring = int(0.55 * SR)  # plucks ring a little past their step, not across chords
    for s, k, chord in note_runs(chords):
        if not chord:
            continue
        put("pad", s * step_samples, soft_pad(chord, k * step_samples + int(0.2 * SR)))
        # a steady figure in eighths, the same every beat: root, third, fifth, third
        notes = sorted(chord)
        figure = [notes[0], notes[1 % len(notes)], notes[2 % len(notes)], notes[1 % len(notes)]]
        for j in range(0, k):
            step = s + j
            if step % 2:
                continue
            m = figure[(step // 2) % 4]
            put("pluck", step * step_samples, pluck(m, ring))

    for s, k, m in note_runs(bass):
        if m >= 0:
            put("bass", s * step_samples, soft_bass(m, k * step_samples))

    kit = soft_drums()
    for s, h in enumerate(hits):
        if h:
            put("drums", s * step_samples, kit[h])

    gains = {
        "lead": 0.17 * lead_level,
        "pluck": 0.13 * chords_level,
        "pad": 0.07 * chords_level,
        "bass": 0.26 * bass_level,
        "drums": 0.16 * drums_level,
    }
    pans = {"lead": 0.1, "pluck": -0.3, "pad": 0.25, "bass": 0.0, "drums": 0.0}
    loop, stems = _stem_mix(ch, gains, pans, length, tail)

    def polish(sig):
        sig = room(sig, mix=0.18 * space)
        cutoff = float(np.clip(7000 * brightness, 400, 16000))
        sig = circular(*butter(2, cutoff, btype="low", fs=SR), sig)
        a = np.exp(-2 * np.pi * 25 / SR)
        return circular([a, -a], [1, -a], sig)

    return _deliver(loop, stems, polish)


# ------------------------------------------------------------------ loop

def render_loop(
    stems: dict,
    *,
    style: str = "soft",
    classic: bool = False,
    lead_from: str = "vocal-melody",
    min_seconds: float = 40.0,
    max_seconds: float = 90.0,
    start_after: float = 0.0,
    space: float = 1.0,
    brightness: float = 1.0,
    lead_level: float = 1.0,
    chords_level: float = 1.0,
    bass_level: float = 1.0,
    drums_level: float = 1.0,
    progress=None,
) -> tuple[np.ndarray, dict]:
    """Transcribe stems and synthesize one seamless loop. Vocal audio is never mixed in."""

    def stage(name: str) -> None:
        if progress:
            progress(name)

    stage("transcribe")
    drums, bass, other = stems["drums"], stems["bass"], stems["other"]
    instrumental = drums + bass + other

    print("Transcribing...")
    bounds = step_grid(instrumental)
    step_sec = float(np.diff(bounds).mean())
    print(f"  tempo ~{60 / step_sec / STEPS_PER_BEAT:.1f} BPM, {len(bounds) - 1} steps")
    key = None
    key_name = None
    if not classic:
        song_chroma = librosa.feature.chroma_cqt(y=instrumental + 0.5 * stems["vocals"], sr=SR, hop_length=HOP).sum(1)
        key = estimate_key(song_chroma)
        names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        key_name = f"{names[key[0]]} {'minor' if key[1] else 'major'}"
        print(f"  key ~{key_name}")
    bass_notes = bass_line(bass, bounds)
    chords, melody = harmony(other, bass, bounds, key)
    if lead_from == "vocal-melody":
        vocal = vocal_melody(stems["vocals"], bounds)
        melody = np.where(vocal >= 0, vocal, melody)
    elif lead_from == "none":
        melody = np.full_like(melody, -1)
    hits = drum_hits(drums, bounds)
    if key is not None:
        scale = scale_of(key)
        bass_notes = bass_follows_chords(snap_to_scale(bass_notes, scale), chords)
        melody = lead_follows_chords(quantize_melody(snap_to_scale(melody, scale)), chords, scale)

    t = librosa.frames_to_time(np.arange(1 + len(instrumental) // HOP), sr=SR, hop_length=HOP)
    chroma = librosa.feature.chroma_cqt(y=instrumental, sr=SR, hop_length=HOP)
    features = np.hstack([
        per_step(chroma, t[: chroma.shape[1]], bounds),
        np.eye(4)[hits] * 0.7,
        np.eye(13)[np.where(bass_notes >= 0, bass_notes % 12, 12)] * 0.7,
    ])
    start, end, score = choose_loop(
        features, step_sec, min_seconds, max_seconds,
        first_step=int(np.searchsorted(bounds, start_after)),
    )
    print(f"  loop: {bounds[start]:.2f}s -> {bounds[end]:.2f}s of the original (match score {score:.3f})")

    stage("render")
    step_samples = int(round(step_sec * SR))
    tone = dict(
        space=space, brightness=brightness, lead_level=lead_level,
        chords_level=chords_level, bass_level=bass_level, drums_level=drums_level,
    )
    if style == "soft" and not classic:
        audio, tracks = render_soft(melody[start:end], chords[start:end], bass_notes[start:end], hits[start:end], step_samples, **tone)
    else:
        audio, tracks = render(melody[start:end], chords[start:end], bass_notes[start:end], hits[start:end], step_samples, classic, **tone)
    info = {
        "bpm": round(60 / step_sec / STEPS_PER_BEAT, 1),
        "key": key_name,
        "loop_start": round(float(bounds[start]), 2),
        "loop_end": round(float(bounds[end]), 2),
        "seconds": round(audio.shape[1] / SR, 1),
    }
    return audio, info, tracks


# ------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", nargs="?", help="path to an .mp3 or a YouTube URL")
    p.add_argument("--stems", help="render straight from a cached stems .npz (skips download and separation)")
    p.add_argument("--name", help="output name (required with --stems)")
    p.add_argument("--style", choices=["soft", "gb"], default="soft",
                   help="'soft' (default): warm instruments, plucked strings, a pad and a small room. "
                        "'gb': 8-bit pulse, wave and noise")
    p.add_argument("--space", type=float, default=1.0, help="room on soft, echo on 8-bit (1 is the usual amount)")
    p.add_argument("--brightness", type=float, default=1.0, help="top end, as a multiple of the usual filter (1 is unchanged)")
    p.add_argument("--lead-level", type=float, default=1.0)
    p.add_argument("--chords-level", type=float, default=1.0)
    p.add_argument("--bass-level", type=float, default=1.0)
    p.add_argument("--drums-level", type=float, default=1.0)
    p.add_argument("--classic", action="store_true",
                   help="the original transcription and mix: no key snapping, raw chords, fast arpeggios, heavier echo")
    p.add_argument("-o", "--out", default="out", help="output directory (default: out)")
    p.add_argument("--min-seconds", type=float, default=40)
    p.add_argument("--max-seconds", type=float, default=90)
    p.add_argument("--start-after", type=float, default=0,
                   help="don't start the loop before this many seconds into the original song")
    p.add_argument("--lead", choices=["vocal-melody", "instrument", "none"], default="vocal-melody",
                   help="where the pulse lead's melody comes from. 'vocal-melody' (default) plays the sung tune "
                        "as a square wave - no voice audio is used - and falls back to the instrument line "
                        "where nobody is singing")
    p.add_argument("--preview", action="store_true", help="also write an MP3 with the loop played 3x to check the seam")
    args = p.parse_args()

    try:
        if args.stems:
            stems = dict(np.load(args.stems))
            name = args.name or Path(args.stems).stem
        else:
            if not args.source:
                raise LoopError("Give a file or a URL.")
            with tempfile.TemporaryDirectory() as tmp:
                is_url = bool(re.match(r"https?://", args.source))
                path = fetch(args.source, Path(tmp))
                name = re.sub(r"[^\w\-]+", "_", youtube_title(args.source) if is_url else path.stem).strip("_")
                stems = separate(path)
        audio, info, _tracks = render_loop(
            stems,
            style=args.style,
            classic=args.classic,
            lead_from=args.lead,
            min_seconds=args.min_seconds,
            max_seconds=args.max_seconds,
            start_after=args.start_after,
            space=args.space,
            brightness=args.brightness,
            lead_level=args.lead_level,
            chords_level=args.chords_level,
            bass_level=args.bass_level,
            drums_level=args.drums_level,
        )
    except LoopError as exc:
        sys.exit(str(exc))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"{name}.wav"
    sf.write(wav, audio.T, SR, subtype="PCM_16")
    ogg = wav.with_suffix(".ogg")
    sf.write(ogg, audio.T, SR, format="OGG", subtype="VORBIS")
    print(f"Wrote {wav} and {ogg} ({info['seconds']:.1f}s loop)")

    if args.preview:
        prev = out_dir / f"{name}.preview.mp3"
        sf.write(out_dir / ".preview.wav", np.tile(audio, 3).T, SR, subtype="PCM_16")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out_dir / ".preview.wav"), "-b:a", "192k", str(prev)], check=True)
        (out_dir / ".preview.wav").unlink()
        print(f"Wrote {prev} (loop x3, for listening to the seam)")


if __name__ == "__main__":
    main()
