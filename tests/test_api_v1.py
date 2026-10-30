import json

import pytest

BLOB = bytes(range(256)) * 40 + b"\r\n--\r\n\r\rend"


def error(response):
    status, _, body = response
    assert status == 400, body
    return json.loads(body)["error"]


def test_sprite_file_with_every_setting(client, started):
    status, _, _ = client.form("/api/v1/sprite", {
        "canvas": "64", "palette_colors": "8", "saturation": "1.5", "contrast": "0.9",
        "coverage": "0.2", "dark_bias": "4", "outline": "false", "sticker": "true",
        "model": "bytedance-seed/seedream-5-0-flash",
    }, file=("cat.png", BLOB))
    assert status == 202
    sprite = started["sprite"]
    assert sprite["bytes"] == BLOB
    assert sprite["name"] == "cat.png"
    assert sprite["model"] == "bytedance-seed/seedream-5-0-flash"
    assert sprite["render"] == {"canvas": 64, "palette_colors": 8, "saturation": 1.5, "contrast": 0.9,
                                "coverage": 0.2, "dark_bias": 4.0, "outline": False, "sticker": True}


def test_sprite_json_url(client, started):
    status, _, _ = client.json("POST", "/api/v1/sprite", {"url": "https://example.com/a.png", "canvas": 32, "outline": False})
    assert status == 202
    assert started["sprite"]["url"] == "https://example.com/a.png"
    assert started["sprite"]["render"]["canvas"] == 32
    assert started["sprite"]["render"]["outline"] is False


@pytest.mark.parametrize("fields, file, message", [
    ({"url": "https://x.com/a.png"}, ("a.png", BLOB), "not both"),
    ({"canvas": "32"}, None, "send a file or a url"),
    ({"url": "https://x.com/a.png", "colours": "8"}, None, "unknown field: colours"),
    ({"url": "https://x.com/a.png", "canvas": "50"}, None, "size must be"),
    ({"url": "https://x.com/a.png", "outline": "maybe"}, None, "outline must be"),
    ({"url": "https://x.com/a.png", "model": "nope"}, None, "pick a model"),
    ({"url": "ftp://x.com/a.png"}, None, "http or https"),
])
def test_sprite_rejects(client, started, fields, file, message):
    assert message in error(client.form("/api/v1/sprite", fields, file=file))
    assert "sprite" not in started


def test_sprite_rejects_other_content_types(client, started):
    response = client.request("POST", "/api/v1/sprite", b"url=https://x.com/a.png",
                              {"Content-Type": "application/x-www-form-urlencoded"})
    assert "multipart/form-data or application/json" in error(response)


def test_loop_file_with_every_setting(client, started):
    status, _, _ = client.form("/api/v1/loop", {
        "rights": "true", "style": "gb", "classic": "true", "lead": "none", "min_seconds": "20",
        "max_seconds": "60", "start_after": "5", "space": "2", "brightness": "0.5", "lead_level": "0",
        "chords_level": "2", "bass_level": "1.5", "drums_level": "0.3",
    }, file=("song.mp3", BLOB))
    assert status == 202
    loop = started["loop"]
    assert loop["bytes"] == BLOB
    assert loop["name"] == "song.mp3"
    assert loop["settings"] == {"style": "gb", "classic": True, "lead": "none", "min_seconds": 20.0,
                                "max_seconds": 60.0, "start_after": 5.0, "space": 2.0, "brightness": 0.5,
                                "lead_level": 0.0, "chords_level": 2.0, "bass_level": 1.5, "drums_level": 0.3}


def test_loop_json_url(client, started):
    status, _, _ = client.json("POST", "/api/v1/loop", {"url": "https://example.com/s.mp3", "rights": True})
    assert status == 202
    assert started["loop"]["url"] == "https://example.com/s.mp3"


@pytest.mark.parametrize("fields, message", [
    ({"url": "https://x.com/s.mp3"}, "confirm you own"),
    ({"url": "https://x.com/s.mp3", "rights": "true", "classic": "maybe"}, "classic must be"),
    ({"url": "https://x.com/s.mp3", "rights": "true", "min_seconds": "100", "max_seconds": "50"}, "shortest loop"),
])
def test_loop_rejects(client, started, fields, message):
    assert message in error(client.form("/api/v1/loop", fields))
    assert "loop" not in started


def test_speech_form_and_json_match(client):
    status, kind, by_form = client.form("/api/v1/speech", {
        "text": "Hello there", "pitch": "440", "speed": "24", "variation": "5", "length": "0.7",
        "drop": "1.4", "pauses": "0.8", "brightness": "8500", "lift": "1.6", "tone": "0.35", "seed": "7",
    })
    assert status == 200
    assert kind == "audio/wav"
    assert by_form[:4] == b"RIFF"
    _, _, by_json = client.json("POST", "/api/v1/speech", {
        "text": "Hello there", "pitch": 440, "speed": 24, "variation": 5, "length": 0.7,
        "drop": 1.4, "pauses": 0.8, "brightness": 8500, "lift": 1.6, "tone": 0.35, "seed": 7,
    })
    assert by_json == by_form


def test_speech_rejects(client):
    assert "type a line" in error(client.form("/api/v1/speech", {"pitch": "300"}))
    assert "not a file" in error(client.form("/api/v1/speech", {"text": "hi"}, file=("a.png", BLOB)))


def test_oversized_request_is_refused_unread(client):
    status, _, body = client.request("POST", "/api/v1/speech", b"x",
                                     {"Content-Type": "application/json", "Content-Length": "999999"})
    assert status == 400
    assert json.loads(body)["error"] == "that request is too large"


def test_unversioned_path_is_gone(client):
    assert client.form("/api/speech", {"text": "hi"})[0] == 404
