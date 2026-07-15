"""Tests for configuration management."""

from pathlib import Path
import pytest
import yaml

from cheapskate.config import Config, DEFAULT_CONFIG, default_memory_dir, ensure_memory_dir


class TestConfig:
    """Tests for the Config class."""

    def test_default_config_loaded_when_no_file(self, tmp_path: Path):
        """When config file doesn't exist, default config should be used."""
        config_path = tmp_path / "nonexistent.yaml"
        config = Config(config_path=config_path)
        # Verify some default values
        assert config.get("capture.auto_capture.ports") is True
        assert config.get("capture.max_per_session") == 50
        assert config.get("forgetting.decay_days") == 90

    def test_custom_config_loaded(self, tmp_path: Path):
        """Custom config file should be loaded correctly."""
        config_path = tmp_path / "config.yaml"
        config_content = """capture:
  auto_capture:
    ports: false
  max_per_session: 100
forgetting:
  decay_days: 30
"""
        config_path.write_text(config_content)

        config = Config(config_path=config_path)
        assert config.get("capture.auto_capture.ports") is False
        assert config.get("capture.max_per_session") == 100
        assert config.get("forgetting.decay_days") == 30

    def test_get_with_default(self, tmp_path: Path):
        """get() should return default for missing keys."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(DEFAULT_CONFIG)
        config = Config(config_path=config_path)

        assert config.get("nonexistent.key") is None
        assert config.get("nonexistent.key", "default") == "default"

    def test_set_value(self, tmp_path: Path):
        """set() should modify configuration in memory."""
        config_path = tmp_path / "config.yaml"
        config = Config(config_path=config_path)

        config.set("test.nested.value", 42)
        assert config.get("test.nested.value") == 42

        config.set("simple", "hello")
        assert config.get("simple") == "hello"

    def test_set_creates_intermediate_dicts(self, tmp_path: Path):
        """set() should create intermediate dictionaries."""
        config = Config()
        config.set("a.b.c.d", "value")
        assert config.get("a.b.c.d") == "value"
        assert isinstance(config._data["a"], dict)
        assert isinstance(config._data["a"]["b"], dict)
        assert isinstance(config._data["a"]["b"]["c"], dict)

    def test_save_and_reload(self, tmp_path: Path):
        """Saving config should persist to file and be reloadable."""
        config_path = tmp_path / "config.yaml"
        config = Config(config_path=config_path)

        config.set("custom.setting", "test_value")
        config.set("another.setting", 123)
        config.save()

        # Reload
        config2 = Config(config_path=config_path)
        assert config2.get("custom.setting") == "test_value"
        assert config2.get("another.setting") == 123

    def test_memory_dir_property(self, tmp_path: Path):
        """memory_dir should return the directory containing config.yaml."""
        config_path = tmp_path / "subdir" / "config.yaml"
        config = Config(config_path=config_path)
        assert config.memory_dir == tmp_path / "subdir"

    def test_database_path_property(self, tmp_path: Path):
        """database_path should be memory_dir/memory.db."""
        config_path = tmp_path / "config.yaml"
        config = Config(config_path=config_path)
        assert config.database_path == tmp_path / "memory.db"

    def test_invalid_yaml_graceful_degradation(self, tmp_path: Path):
        """Invalid YAML should not crash the config loader."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("invalid: yaml: content: [")
        # This should not raise; it falls back to default
        config = Config(config_path=config_path)
        # Should have default values, not the invalid ones
        assert config.get("capture.max_per_session") == 50  # from default

    def test_empty_config_file_uses_defaults(self, tmp_path: Path):
        """Empty config file should fall back to defaults."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")
        config = Config(config_path=config_path)
        assert config.get("forgetting.decay_days") == 90


class TestDefaultMemoryDir:
    """Tests for default_memory_dir function."""

    def test_returns_home_dot_memory(self):
        """default_memory_dir should return ~/.memory."""
        mem_dir = default_memory_dir()
        assert mem_dir == Path.home() / ".memory"


class TestEnsureMemoryDir:
    """Tests for ensure_memory_dir function."""

    def test_creates_directory_if_missing(self, tmp_path: Path):
        """Should create the directory if it doesn't exist."""
        target_dir = tmp_path / "new" / "nested" / "memory"
        assert not target_dir.exists()
        result = ensure_memory_dir(target_dir)
        assert result == target_dir
        assert target_dir.exists()

    def test_returns_existing_directory(self, tmp_path: Path):
        """Should return the path if it already exists."""
        existing = tmp_path / "memory"
        existing.mkdir()
        result = ensure_memory_dir(existing)
        assert result == existing


class TestConfigYAMLFormat:
    """Tests for YAML format validation."""

    def test_default_config_is_valid_yaml(self):
        """DEFAULT_CONFIG constant should be valid YAML."""
        parsed = yaml.safe_load(DEFAULT_CONFIG)
        assert isinstance(parsed, dict)
        assert "capture" in parsed
        assert "consolidate" in parsed
        assert "forgetting" in parsed
