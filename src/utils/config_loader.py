"""Configuration loader with validation and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ModelConfig:
    """Model configuration."""
    name: str
    weight: float
    enabled: bool = True
    dtype: str = "float32"
    num_samples: int = 100
    patch_size: str = "auto"


@dataclass
class HorizonConfig:
    """Horizon configuration."""
    context_length: int
    prediction_length: int
    weight: float
    return_cap: float


@dataclass
class DataConfig:
    """Data collection configuration."""
    collection_days: int = 150
    min_trading_days: int = 120
    recent_trading_days: int = 5
    max_workers: int = 8
    retry_count: int = 3
    cache_expiry_hours: int = 24
    anomaly_threshold: float = 0.30


@dataclass
class FilterConfig:
    """Filter configuration."""
    min_volume: int = 50000
    min_value: int = 500000000
    max_sector_count: int = 3
    top_n: int = 15
    exclude_etf: bool = True
    exclude_etn: bool = True
    exclude_spac: bool = True
    exclude_reits: bool = True


@dataclass
class ScoringConfig:
    """Scoring configuration."""
    direction_weight: float = 0.60
    magnitude_weight: float = 0.40
    return_weight: float = 0.70
    agreement_weight: float = 0.30
    freq_bonus_factor: float = 0.02


@dataclass
class PathConfig:
    """Path configuration."""
    output_dir: str = "outputs"
    log_dir: str = "logs"
    cache_dir: str = "cache"


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    console_format: str = "rich"
    file_format: str = "detailed"


@dataclass
class Config:
    """Main configuration container."""
    models: dict[str, ModelConfig] = field(default_factory=dict)
    horizons: dict[str, HorizonConfig] = field(default_factory=dict)
    data: DataConfig = field(default_factory=DataConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def get_enabled_models(self) -> list[str]:
        """Return list of enabled model names."""
        return [name for name, cfg in self.models.items() if cfg.enabled]

    def get_model_weights(self) -> dict[str, float]:
        """Return enabled model weights, normalized to sum to 1."""
        enabled = {name: cfg.weight for name, cfg in self.models.items() if cfg.enabled}
        total = sum(enabled.values())
        if total > 0:
            return {name: w / total for name, w in enabled.items()}
        return enabled

    def get_horizon_weights(self) -> dict[str, float]:
        """Return horizon weights."""
        return {name: cfg.weight for name, cfg in self.horizons.items()}


class ConfigValidationError(Exception):
    """Configuration validation error."""
    pass


def _validate_weights(weights: dict[str, float], name: str, tolerance: float = 0.01) -> None:
    """Validate that weights sum to approximately 1.0."""
    total = sum(weights.values())
    if abs(total - 1.0) > tolerance:
        raise ConfigValidationError(
            f"{name} weights must sum to 1.0, got {total:.2f}"
        )


def _validate_positive(value: float | int, name: str) -> None:
    """Validate that value is positive."""
    if value <= 0:
        raise ConfigValidationError(f"{name} must be positive, got {value}")


def _validate_range(value: float, min_val: float, max_val: float, name: str) -> None:
    """Validate that value is within range."""
    if not min_val <= value <= max_val:
        raise ConfigValidationError(
            f"{name} must be between {min_val} and {max_val}, got {value}"
        )


def validate_config(config: Config) -> None:
    """Validate configuration values."""
    # Validate model weights
    model_weights = {name: cfg.weight for name, cfg in config.models.items() if cfg.enabled}
    if model_weights:
        _validate_weights(model_weights, "Model")

    # Validate horizon weights
    horizon_weights = {name: cfg.weight for name, cfg in config.horizons.items()}
    if horizon_weights:
        _validate_weights(horizon_weights, "Horizon")

    # Validate scoring weights
    _validate_range(config.scoring.direction_weight, 0, 1, "direction_weight")
    _validate_range(config.scoring.magnitude_weight, 0, 1, "magnitude_weight")
    _validate_range(config.scoring.return_weight, 0, 1, "return_weight")
    _validate_range(config.scoring.agreement_weight, 0, 1, "agreement_weight")

    # Validate data config
    _validate_positive(config.data.collection_days, "collection_days")
    _validate_positive(config.data.min_trading_days, "min_trading_days")

    # Validate filter config
    _validate_positive(config.filters.min_volume, "min_volume")
    _validate_positive(config.filters.min_value, "min_value")
    _validate_positive(config.filters.top_n, "top_n")


def _parse_model_config(data: dict[str, Any]) -> dict[str, ModelConfig]:
    """Parse model configuration from dict."""
    models = {}
    for name, cfg in data.items():
        models[name] = ModelConfig(
            name=cfg.get("name", ""),
            weight=cfg.get("weight", 0.0),
            enabled=cfg.get("enabled", True),
            dtype=cfg.get("dtype", "float32"),
            num_samples=cfg.get("num_samples", 100),
            patch_size=cfg.get("patch_size", "auto"),
        )
    return models


def _parse_horizon_config(data: dict[str, Any]) -> dict[str, HorizonConfig]:
    """Parse horizon configuration from dict."""
    horizons = {}
    for name, cfg in data.items():
        horizons[name] = HorizonConfig(
            context_length=cfg.get("context_length", 60),
            prediction_length=cfg.get("prediction_length", 20),
            weight=cfg.get("weight", 0.0),
            return_cap=cfg.get("return_cap", 0.5),
        )
    return horizons


def load_config(config_path: str | Path) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config YAML file

    Returns:
        Validated Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ConfigValidationError: If configuration is invalid
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    # Parse configuration sections
    config = Config(
        models=_parse_model_config(raw_config.get("models", {})),
        horizons=_parse_horizon_config(raw_config.get("horizons", {})),
        data=DataConfig(**raw_config.get("data", {})),
        filters=FilterConfig(**raw_config.get("filters", {})),
        scoring=ScoringConfig(**raw_config.get("scoring", {})),
        paths=PathConfig(**raw_config.get("paths", {})),
        logging=LoggingConfig(**raw_config.get("logging", {})),
    )

    # Validate
    validate_config(config)

    # Ensure directories exist
    base_path = config_path.parent.parent
    for dir_name in [config.paths.output_dir, config.paths.log_dir, config.paths.cache_dir]:
        dir_path = base_path / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)

    return config


def get_default_config() -> Config:
    """Get default configuration."""
    return Config(
        models={
            "chronos": ModelConfig(
                name="amazon/chronos-bolt-small",
                weight=0.40,
                dtype="bfloat16",
            ),
            "ttm": ModelConfig(
                name="ibm-granite/granite-timeseries-ttm-r2",
                weight=0.35,
            ),
            "moirai": ModelConfig(
                name="Salesforce/moirai-1.0-R-small",
                weight=0.25,
                num_samples=100,
            ),
        },
        horizons={
            "short": HorizonConfig(
                context_length=20,
                prediction_length=5,
                weight=0.50,
                return_cap=0.30,
            ),
            "mid": HorizonConfig(
                context_length=60,
                prediction_length=20,
                weight=0.30,
                return_cap=0.50,
            ),
            "long": HorizonConfig(
                context_length=120,
                prediction_length=60,
                weight=0.20,
                return_cap=1.00,
            ),
        },
    )
