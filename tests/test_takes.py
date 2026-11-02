"""Several takes from one job, and the MIDI each one carries."""

import io
import json
import threading
import zipfile

import numpy as np
import pytest
import soundfile as sf

from app import audio_jobs

JOB = "0123456789abcdef"
SR = 44100


class FakeRetro:
    SR = SR

    def separate(self, path):
        return {}

    def render_takes(self, stems, takes, **_options):
        tone = np.zeros((2, SR // 10))
        return [
            {
                "audio": tone,
                "tracks": {"lead": tone, "bass": tone},
                "midi": b"MThd-%d" % number,
                "info": {"bpm": 120.0, "key": "C major", "loop_start": number, "loop_end": number + 8, "seconds": 8.0},
            }
            for number in range(1, takes + 1)
        ]


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setattr(audio_jobs, "AUDIO", tmp_path)
    monkeypatch.setattr(audio_jobs, "_retroloop", FakeRetro)
    folder = tmp_path / JOB
    folder.mkdir()
    source = folder / "source.wav"
    settings = audio_jobs.parse_settings({"takes": 2})
    audio_jobs._save(folder, audio_jobs._running(JOB, "My Song", "queued", settings))
    audio_jobs._worker(JOB, None, source, threading.Lock())
    return folder


def test_view_lists_each_take(job):
    viewed = audio_jobs.view(JOB)
    assert viewed["status"] == "done", viewed["error"]
    assert [take["number"] for take in viewed["takes"]] == [1, 2]
    assert viewed["takes"][0]["files"] == viewed["files"]
    second = viewed["takes"][1]
    assert second["info"]["loop_start"] == 2
    assert second["files"]["wav"].endswith("/take2-loop.wav")
    assert second["files"]["midi"].endswith("/take2-loop.mid")
    assert [track["id"] for track in second["files"]["tracks"]] == ["lead", "bass"]
    assert "take_info" not in viewed


def test_each_take_has_its_own_package(job):
    body, kind, download = audio_jobs.file_bytes(JOB, "take2-score.zip")
    assert kind == "application/zip"
    assert download == "My-Song-take2.zip"
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert archive.read("loop.mid") == b"MThd-2"
        assert sorted(archive.namelist()) == ["bass.wav", "kaldr-settings.json", "lead.wav", "loop.mid", "loop.ogg", "loop.wav"]
        assert json.loads(archive.read("kaldr-settings.json"))["loop"]["takes"] == 2


def test_take_one_keeps_its_old_addresses(job):
    assert audio_jobs.file_bytes(JOB, "loop.wav")[1] == "audio/wav"
    assert audio_jobs.file_bytes(JOB, "score.zip")[2] == "My-Song.zip"


@pytest.mark.parametrize("name", ["take3-loop.wav", "take2-status.json", "status.json", "../status.json", "take2-source.wav"])
def test_other_files_stay_private(job, name):
    assert audio_jobs.file_bytes(JOB, name) is None


def test_a_job_from_before_takes_still_opens(job):
    status = json.loads((job / "status.json").read_text())
    del status["take_info"]
    (job / "status.json").write_text(json.dumps(status))
    viewed = audio_jobs.view(JOB)
    assert [take["number"] for take in viewed["takes"]] == [1]
    assert viewed["takes"][0]["info"] == status["info"]


def test_wavs_read_back(job):
    audio, rate = sf.read(io.BytesIO(audio_jobs.file_bytes(JOB, "take2-lead.wav")[0]))
    assert rate == SR
    assert audio.shape == (SR // 10, 2)


# ---------------------------------------------------------------- the real thing

retroloop = pytest.importorskip("retroloop.retroloop")


def repeating_features(bars: int = 80, sections: int = 4) -> np.ndarray:
    """A song that cycles through sections of 8 distinct bars, so any 8-bar span loops well."""
    rng = np.random.default_rng(1)
    patterns = rng.random((sections * 8, 16))
    return np.vstack([np.tile(patterns[bar % len(patterns)], (16, 1)) for bar in range(bars)])


def test_first_take_is_the_old_pick():
    features = repeating_features()
    one = retroloop.choose_loops(features, 0.1, 10, 30)
    three = retroloop.choose_loops(features, 0.1, 10, 30, count=3)
    assert len(one) == 1
    assert three[0] == one[0]


def test_takes_are_different_sections_of_the_song():
    chosen = retroloop.choose_loops(repeating_features(), 0.1, 10, 30, count=3)
    assert len(chosen) == 3
    for index, take in enumerate(chosen):
        assert (take[1] - take[0]) % retroloop.STEPS_PER_BAR == 0
        for earlier in chosen[:index]:
            assert retroloop._overlap(take, earlier) < retroloop.TAKE_OVERLAP


def test_a_song_with_one_good_section_returns_one_take():
    rng = np.random.default_rng(2)
    features = rng.random((16 * 40, 16))
    features[160:208] = features[320:368]  # only one spot where the music repeats
    chosen = retroloop.choose_loops(features, 0.1, 10, 20, count=3)
    assert len(chosen) == 1


def test_midi_is_a_valid_file_with_every_part():
    lead = np.array([60, 60, -1, 62] * 8)
    bass = np.array([36] * 32)
    chords = [(57, 60, 64)] * 32
    hits = np.array([3, 0, 1, 0, 2, 0, 1, 0] * 4)
    data = retroloop.midi_bytes(lead, chords, bass, hits, 0.125)

    assert data[:4] == b"MThd"
    assert int.from_bytes(data[8:10], "big") == 1
    assert int.from_bytes(data[10:12], "big") == 4
    assert int.from_bytes(data[12:14], "big") == retroloop.MIDI_TICKS_PER_STEP * retroloop.STEPS_PER_BEAT
    assert data.count(b"MTrk") == 4
    for name in (b"Lead", b"Chords", b"Bass", b"Drums"):
        assert name in data
    # 0.125s a step is 0.5s a beat, 120 BPM
    assert (500000).to_bytes(3, "big") in data
    assert bytes([0x99, 36, 96]) in data  # a kick on the drum channel


def slow_room(loop, mix=0.18):
    """The room as plain time-domain filters over two passes of the loop. What the fast one must match."""
    from scipy.signal import butter, lfilter

    rate = retroloop.SR
    wet = np.zeros_like(loop)
    for ch in range(2):
        x = loop[ch]
        acc = np.zeros_like(x)
        for ms in (29.7, 37.1, 41.1, 43.7):
            d = int(ms * rate / 1000) + ch * 7
            a = np.zeros(d + 1)
            a[0], a[d] = 1.0, -0.72
            acc += lfilter([1.0], a, np.concatenate([x, x]))[len(x):]
        for ms in (5.0, 1.7):
            d = int(ms * rate / 1000)
            b = np.zeros(d + 1)
            a = np.zeros(d + 1)
            b[0], b[d] = -0.6, 1.0
            a[0], a[d] = 1.0, -0.6
            acc = lfilter(b, a, np.concatenate([acc, acc]))[len(acc):]
        wet[ch] = acc / 4
    wet = retroloop.circular(*butter(1, 3500, btype="low", fs=rate), wet)
    return loop + mix * wet


def test_fast_room_sounds_the_same_as_the_slow_filters():
    rng = np.random.default_rng(3)
    # Long enough for the slow filters to settle within their two passes, as a real loop does.
    loop = rng.uniform(-1, 1, (2, retroloop.SR * 2))
    assert np.abs(retroloop.room(loop) - slow_room(loop)).max() < 1e-6
