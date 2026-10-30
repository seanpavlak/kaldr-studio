import pytest

from app.http_base import local_name


@pytest.mark.parametrize("value", ["127.0.0.1", "127.0.0.1:5173", "localhost", "localhost:8765", "[::1]:8765"])
def test_local_hosts(value):
    assert local_name(value)


@pytest.mark.parametrize("value", [None, "", "evil.com", "localhost.evil.com", "127.0.0.1.evil.com", "[bad"])
def test_other_hosts(value):
    assert not local_name(value)


def test_origins():
    assert local_name("http://127.0.0.1:5173", url=True)
    assert not local_name("https://evil.com", url=True)
    assert not local_name("null", url=True)


def test_server_refuses_other_hosts(client):
    assert client.request("GET", "/models")[0] == 200
    assert client.request("GET", "/models", headers={"Host": "evil.com"})[0] == 403
    assert client.request("GET", "/models", headers={"Origin": "https://evil.com"})[0] == 403
    assert client.request("GET", "/models", headers={"Origin": "http://localhost:5173"})[0] == 200
    status, _, _ = client.json("PUT", "/openrouter-key", {"key": "x" * 40}, headers={"Origin": "https://evil.com"})
    assert status == 403
