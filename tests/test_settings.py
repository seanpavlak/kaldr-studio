"""The one settings file, and the copy of it in each package."""

import io
import json
import zipfile

import pytest

from app import pipeline, settings, sprite_jobs


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def saved_path(home):
    return home / "Library/Application Support/kaldr-studio/kaldr-settings.json"


def test_defaults_cover_every_builder(client):
    status, _, body = client.request("GET", "/settings")
    assert status == 200
    doc = json.loads(body)
    assert doc["version"] == 1
    assert doc["sprite"]["model"] == pipeline.DEFAULT_MODEL
    assert doc["sprite"]["canvas"] == 48
    assert doc["loop"]["style"] == "soft"
    assert doc["speech"]["pitch"] == 300
    assert "text" not in doc["speech"]


def test_saving_one_section_keeps_the_others(client, home):
    client.json("PUT", "/settings", {"loop": {"style": "gb"}})
    status, _, body = client.json("PUT", "/settings", {"speech": {"pitch": 440, "text": "not kept"}})
    assert status == 200
    doc = json.loads(body)
    assert doc["loop"]["style"] == "gb"
    assert doc["speech"]["pitch"] == 440
    on_disk = json.loads(saved_path(home).read_text())
    assert on_disk == doc
    assert "not kept" not in saved_path(home).read_text()


def test_export_downloads_what_is_saved(client):
    client.json("PUT", "/settings", {"sprite": {"canvas": 64, "model": pipeline.DEFAULT_MODEL}})
    status, kind, body = client.request("GET", "/settings/kaldr-settings.json")
    assert status == 200
    assert kind.startswith("application/json")
    assert json.loads(body)["sprite"]["canvas"] == 64


@pytest.mark.parametrize("payload, message", [
    ({"nope": {}}, "unknown settings: nope"),
    ({"sprite": {"canvas": 50}}, "size must be"),
    ({"sprite": {"model": "nope"}}, "pick a model"),
    ({"loop": {"takes": 9}}, "takes"),
    ({"speech": {"pitch": 1}}, "pitch"),
    ({"speech": "loud"}, "must be an object"),
])
def test_bad_settings_are_refused_and_not_saved(client, home, payload, message):
    status, _, body = client.json("PUT", "/settings", payload)
    assert status == 400
    assert message in json.loads(body)["error"]
    assert not saved_path(home).exists()


@pytest.mark.parametrize("text", ["not json", "[]", '{"loop": {"style": "loud"}}'])
def test_a_damaged_file_falls_back_to_defaults(home, text):
    settings.load()
    saved_path(home).write_text(text)
    assert settings.load()["loop"]["style"] == "soft"


def test_sprite_package_carries_its_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(sprite_jobs, "JOBS", tmp_path)
    job = tmp_path / "abc"
    job.mkdir()
    (job / "status.json").write_text(json.dumps({"id": "abc", "model": "m", "render": {"canvas": 32}, "status": "done"}))
    source = sprite_jobs.BUNDLE[0][0]
    (job / source).write_bytes(b"x")
    with zipfile.ZipFile(io.BytesIO(sprite_jobs.bundle("abc"))) as archive:
        packed = json.loads(archive.read("kaldr-settings.json"))
    assert packed["sprite"] == {"model": "m", "canvas": 32}
