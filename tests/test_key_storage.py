import stat

from app import pipeline


def test_key_moves_from_the_old_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.Path, "home", classmethod(lambda cls: tmp_path))
    old = tmp_path / "Library/Application Support/sprite-studio"
    old.mkdir(parents=True)
    (old / "openrouter.key").write_text("sk-or-v1-" + "a" * 40)

    path = pipeline._key_path()

    assert path == tmp_path / "Library/Application Support/kaldr-studio/openrouter.key"
    assert path.read_text() == "sk-or-v1-" + "a" * 40
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert not old.exists()


def test_new_key_wins_over_old(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.Path, "home", classmethod(lambda cls: tmp_path))
    support = tmp_path / "Library/Application Support"
    (support / "sprite-studio").mkdir(parents=True)
    (support / "sprite-studio" / "openrouter.key").write_text("old")
    (support / "kaldr-studio").mkdir()
    (support / "kaldr-studio" / "openrouter.key").write_text("new")

    assert pipeline._key_path().read_text() == "new"
    assert (support / "sprite-studio" / "openrouter.key").exists()


def test_save_and_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.Path, "home", classmethod(lambda cls: tmp_path))
    pipeline.save_openrouter_key("sk-or-v1-abcdefghijklmnopqrstuvwxyz")
    assert pipeline.openrouter_key_hint() == "sk-or-v1-abc...xyz"
    pipeline.clear_openrouter_key()
    assert not pipeline.openrouter_key_saved()
