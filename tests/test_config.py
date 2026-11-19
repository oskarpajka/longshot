import pytest

from longshot.config import ConfigError, config_hash, load_config


def test_load_config_requires_stage_and_name(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("stage: search\n")
    with pytest.raises(ConfigError):
        load_config(p)


def test_load_config_ok(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("stage: search\nrun_name: x\nsnr_min: 7.5\n")
    cfg = load_config(p)
    assert cfg["snr_min"] == 7.5


def test_config_hash_is_order_independent():
    assert config_hash({"a": 1, "b": [1, 2]}) == config_hash({"b": [1, 2], "a": 1})
    assert config_hash({"a": 1}) != config_hash({"a": 2})
