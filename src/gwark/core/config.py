"""Configuration loading and management for gwark."""

from pathlib import Path
from typing import Optional

import yaml

from gwark.schemas.config import GwarkConfig, ProfileConfig

# Default config directory name
CONFIG_DIR = ".gwark"
CONFIG_FILE = "config.yaml"
PROFILES_DIR = "profiles"


def find_config_dir(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find the .gwark config directory by walking up from start_path.

    Args:
        start_path: Starting directory (defaults to cwd)

    Returns:
        Path to .gwark directory or None if not found
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    while current != current.parent:
        config_dir = current / CONFIG_DIR
        if config_dir.is_dir():
            return config_dir
        current = current.parent

    return None


def load_config(config_path: Optional[Path] = None) -> GwarkConfig:
    """Load the main configuration file.

    Args:
        config_path: Explicit path to config.yaml (optional)

    Returns:
        GwarkConfig instance with loaded or default values
    """
    if config_path is None:
        config_dir = find_config_dir()
        if config_dir:
            config_path = config_dir / CONFIG_FILE

    if config_path and config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return GwarkConfig(**data)

    # Return default config
    return GwarkConfig()


def get_profile(profile_name: str, config_dir: Optional[Path] = None) -> ProfileConfig:
    """Load a named profile from the profiles directory.

    Args:
        profile_name: Name of the profile to load
        config_dir: Path to .gwark directory (optional)

    Returns:
        ProfileConfig instance
    """
    if config_dir is None:
        config_dir = find_config_dir()

    if config_dir:
        profile_path = config_dir / PROFILES_DIR / f"{profile_name}.yaml"
        if profile_path.exists():
            with open(profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            data["name"] = profile_name
            return ProfileConfig(**data)

    # Return default profile
    return ProfileConfig(name=profile_name)


def get_active_profile(config: Optional[GwarkConfig] = None) -> ProfileConfig:
    """Get the currently active profile.

    Args:
        config: GwarkConfig instance (optional, will load if not provided)

    Returns:
        ProfileConfig for the active profile
    """
    if config is None:
        config = load_config()

    return get_profile(config.active_profile)


def save_config(config: GwarkConfig, config_path: Optional[Path] = None) -> Path:
    """Save configuration to file.

    Args:
        config: GwarkConfig to save
        config_path: Path to save to (optional)

    Returns:
        Path where config was saved
    """
    if config_path is None:
        config_dir = find_config_dir() or Path.cwd() / CONFIG_DIR
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / CONFIG_FILE

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)

    return config_path


def save_profile(profile: ProfileConfig, config_dir: Optional[Path] = None) -> Path:
    """Save a profile to file.

    Args:
        profile: ProfileConfig to save
        config_dir: Path to .gwark directory (optional)

    Returns:
        Path where profile was saved
    """
    if config_dir is None:
        config_dir = find_config_dir() or Path.cwd() / CONFIG_DIR

    profiles_dir = config_dir / PROFILES_DIR
    profiles_dir.mkdir(parents=True, exist_ok=True)

    profile_path = profiles_dir / f"{profile.name}.yaml"

    with open(profile_path, "w", encoding="utf-8") as f:
        yaml.dump(profile.model_dump(), f, default_flow_style=False, sort_keys=False)

    return profile_path


def init_config_dir(path: Optional[Path] = None, force: bool = False) -> Path:
    """Initialize a new .gwark configuration directory.

    Args:
        path: Where to create .gwark (defaults to cwd)
        force: Overwrite existing config

    Returns:
        Path to created .gwark directory

    Raises:
        FileExistsError: If config exists and force=False
    """
    if path is None:
        path = Path.cwd()

    config_dir = path / CONFIG_DIR

    if config_dir.exists() and not force:
        raise FileExistsError(f"Config directory already exists: {config_dir}")

    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / PROFILES_DIR).mkdir(exist_ok=True)

    # Create default config
    config = GwarkConfig()
    save_config(config, config_dir / CONFIG_FILE)

    # Create default profile
    default_profile = ProfileConfig(
        name="default",
        description="Default profile with no filters",
    )
    save_profile(default_profile, config_dir)

    return config_dir
