"""Unit tests for gwark.core.config."""

import pytest
from pathlib import Path

from gwark.core.config import find_config_dir, load_config
from gwark.schemas.config import GwarkConfig


class TestFindConfigDir:
    def test_finds_gwark_dir(self, tmp_path):
        gwark_dir = tmp_path / ".gwark"
        gwark_dir.mkdir()
        result = find_config_dir(tmp_path)
        assert result == gwark_dir

    def test_returns_none_when_missing(self, tmp_path):
        # Use a deeply nested path that won't have .gwark anywhere above
        isolated = tmp_path / "no_gwark_here" / "deep"
        isolated.mkdir(parents=True)
        result = find_config_dir(isolated)
        # May find user-level .gwark — just verify it's not in our tmp dir
        if result is not None:
            assert not str(result).startswith(str(tmp_path))

    def test_walks_up_directories(self, tmp_path):
        gwark_dir = tmp_path / ".gwark"
        gwark_dir.mkdir()
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        result = find_config_dir(nested)
        assert result == gwark_dir


class TestLoadConfig:
    def test_default_config(self):
        config = load_config(config_path=Path("/nonexistent/config.yaml"))
        assert isinstance(config, GwarkConfig)

    def test_loads_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("defaults:\n  days_back: 90\n")
        config = load_config(config_path=config_file)
        assert config.defaults.days_back == 90

    def test_empty_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = load_config(config_path=config_file)
        assert isinstance(config, GwarkConfig)
