"""The routes the studio page itself calls."""

import json

from tests.conftest import JOB_ID


def test_models(client):
    status, _, body = client.request("GET", "/models")
    assert status == 200
    assert json.loads(body)["default"]


def test_unknown_routes_are_json_404s(client):
    for method, path in [("GET", "/nope"), ("POST", "/nope"), ("PUT", "/nope"), ("DELETE", "/nope"),
                         ("GET", "/jobs/not-an-id"), ("POST", "/jobs/not-an-id/render")]:
        status, kind, _ = client.request(method, path, b"{}", {"Content-Type": "application/json"})
        assert status == 404, (method, path)
        assert kind.startswith("application/json")


def test_job_from_url(client, started):
    status, _, body = client.json("POST", "/jobs", {"url": "https://example.com/a.png", "render": {"canvas": 32}})
    assert status == 202
    assert json.loads(body)["id"] == JOB_ID
    assert started["sprite"]["render"]["canvas"] == 32


def test_job_rejects_bad_url(client, started):
    status, _, body = client.json("POST", "/jobs", {"url": "file:///etc/passwd"})
    assert status == 400
    assert "http or https" in json.loads(body)["error"]


def test_job_from_file_headers(client, started):
    status, _, _ = client.request("POST", "/jobs/file", b"image bytes", {
        "X-Sprite-Name": "cat.png", "X-Sprite-Render": json.dumps({"sticker": True}),
    })
    assert status == 202
    assert started["sprite"]["name"] == "cat.png"
    assert started["sprite"]["render"]["sticker"] is True


def test_rerender_checks_settings_then_job(client):
    status, _, body = client.json("POST", "/jobs/ffffffffffffffff/render", {"render": {"canvas": 50}})
    assert status == 400
    status, _, body = client.json("POST", "/jobs/ffffffffffffffff/render", {"render": {}})
    assert status == 404


def test_key_rejects_a_bad_key_without_saving(client):
    status, _, body = client.json("PUT", "/openrouter-key", {"key": "short"})
    assert status == 400
    assert "OpenRouter key" in json.loads(body)["error"]
