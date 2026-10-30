import pytest

from app import audio_jobs, pipeline


def test_render_defaults():
    assert pipeline.parse_render(None) == pipeline.default_render()


@pytest.mark.parametrize("raw", [
    {"canvas": 50},
    {"palette_colors": 3},
    {"palette_colors": 4.5},
    {"saturation": 2.1},
    {"outline": "yes"},
    {"canvas": True},
    {"colours": 8},
])
def test_render_rejects(raw):
    with pytest.raises(ValueError):
        pipeline.parse_render(raw)


def test_model_defaults_and_rejects_unknown():
    assert pipeline.parse_model(None) == pipeline.DEFAULT_MODEL
    assert pipeline.parse_model("") == pipeline.DEFAULT_MODEL
    with pytest.raises(ValueError):
        pipeline.parse_model("nope")


def test_loop_settings():
    assert audio_jobs.parse_settings(None)["style"] == "soft"
    with pytest.raises(ValueError, match="shortest loop"):
        audio_jobs.parse_settings({"min_seconds": 100, "max_seconds": 50})
    with pytest.raises(ValueError, match="style"):
        audio_jobs.parse_settings({"style": "loud"})


def test_speech_settings():
    assert audio_jobs.parse_speak({"text": " hi ", "seed": ""}) | {} == audio_jobs.parse_speak({"text": "hi"})
    with pytest.raises(ValueError, match="type a line"):
        audio_jobs.parse_speak({"text": "   "})
    with pytest.raises(ValueError, match="whole number"):
        audio_jobs.parse_speak({"text": "hi", "seed": "1.5"})
    with pytest.raises(ValueError, match="600"):
        audio_jobs.parse_speak({"text": "a" * 601})
