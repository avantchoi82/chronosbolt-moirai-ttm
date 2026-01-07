"""Data preprocessor with validation and scaling."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.utils.config_loader import DataConfig

logger = logging.getLogger("ensemble")


@dataclass
class ValidationResult:
    """Result of data validation."""
    valid: bool
    code: str
    trading_days: int
    has_recent_trading: bool
    anomaly_dates: list[str]
    error: str | None = None


@dataclass
class ScalerParams:
    """Parameters for Standard Scaler."""
    mean: float
    std: float


class StandardScaler:
    """Standard scaler for TTM model input."""

    def __init__(self):
        self.params: dict[str, ScalerParams] = {}

    def fit(self, data: pd.DataFrame, columns: list[str] | None = None) -> "StandardScaler":
        """Fit scaler to data.

        Args:
            data: DataFrame to fit
            columns: Columns to scale (default: all numeric)

        Returns:
            Self for chaining
        """
        if columns is None:
            columns = data.select_dtypes(include=[np.number]).columns.tolist()

        for col in columns:
            self.params[col] = ScalerParams(
                mean=float(data[col].mean()),
                std=float(data[col].std()),
            )

        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data using fitted parameters.

        Args:
            data: DataFrame to transform

        Returns:
            Scaled DataFrame
        """
        result = data.copy()
        for col, params in self.params.items():
            if col in result.columns:
                if params.std > 0:
                    result[col] = (result[col] - params.mean) / params.std
                else:
                    result[col] = result[col] - params.mean
        return result

    def fit_transform(self, data: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
        """Fit and transform in one step.

        Args:
            data: DataFrame to fit and transform
            columns: Columns to scale

        Returns:
            Scaled DataFrame
        """
        return self.fit(data, columns).transform(data)

    def inverse_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Reverse the scaling transformation.

        Args:
            data: Scaled DataFrame

        Returns:
            Original scale DataFrame
        """
        result = data.copy()
        for col, params in self.params.items():
            if col in result.columns:
                result[col] = result[col] * params.std + params.mean
        return result

    def inverse_transform_value(self, value: float, column: str) -> float:
        """Reverse scaling for a single value.

        Args:
            value: Scaled value
            column: Column name

        Returns:
            Original scale value
        """
        if column in self.params:
            params = self.params[column]
            return value * params.std + params.mean
        return value


def handle_missing_values(
    df: pd.DataFrame,
    method: str = "drop",
) -> pd.DataFrame:
    """Handle missing values in OHLCV data.

    Args:
        df: DataFrame with OHLCV data
        method: "drop" for stocks, "ffill" for macro

    Returns:
        DataFrame with handled missing values
    """
    result = df.copy()

    if method == "drop":
        # Drop rows with any missing values
        result = result.dropna()
    elif method == "ffill":
        # Forward fill for macro indicators
        result = result.ffill().bfill()

    return result


def detect_anomalies(
    df: pd.DataFrame,
    threshold: float = 0.30,
) -> list[str]:
    """Detect anomalous price changes.

    Args:
        df: DataFrame with OHLCV data
        threshold: Maximum allowed daily change (e.g., 0.30 for 30%)

    Returns:
        List of dates with anomalies
    """
    anomaly_dates = []

    if "close" not in df.columns:
        return anomaly_dates

    # Calculate daily returns
    returns = df["close"].pct_change()

    # Find dates with returns exceeding threshold
    anomalies = returns.abs() > threshold
    if anomalies.any():
        anomaly_indices = df.index[anomalies]
        if "date" in df.columns:
            anomaly_dates = df.loc[anomaly_indices, "date"].astype(str).tolist()
        else:
            anomaly_dates = [str(i) for i in anomaly_indices]

    return anomaly_dates


def validate_data(
    df: pd.DataFrame,
    code: str,
    min_trading_days: int = 120,
    recent_days: int = 5,
    anomaly_threshold: float = 0.30,
) -> ValidationResult:
    """Validate stock data according to CONSTITUTION.md rules.

    Args:
        df: DataFrame with OHLCV data
        code: Stock code
        min_trading_days: Minimum required trading days (제10조)
        recent_days: Days to check for recent trading (제10조)
        anomaly_threshold: Anomaly detection threshold (제10조)

    Returns:
        ValidationResult
    """
    if df is None or df.empty:
        return ValidationResult(
            valid=False,
            code=code,
            trading_days=0,
            has_recent_trading=False,
            anomaly_dates=[],
            error="No data",
        )

    trading_days = len(df)

    # Check minimum trading days
    if trading_days < min_trading_days:
        return ValidationResult(
            valid=False,
            code=code,
            trading_days=trading_days,
            has_recent_trading=False,
            anomaly_dates=[],
            error=f"Insufficient trading days: {trading_days} < {min_trading_days}",
        )

    # Check recent trading activity
    has_recent_trading = True
    if "date" in df.columns:
        last_date = pd.to_datetime(df["date"].iloc[-1])
        cutoff_date = datetime.now() - timedelta(days=recent_days + 2)  # Buffer for weekends
        has_recent_trading = last_date >= cutoff_date

    # Detect anomalies
    anomaly_dates = detect_anomalies(df, anomaly_threshold)

    return ValidationResult(
        valid=trading_days >= min_trading_days and has_recent_trading,
        code=code,
        trading_days=trading_days,
        has_recent_trading=has_recent_trading,
        anomaly_dates=anomaly_dates,
    )


class DataPreprocessor:
    """Preprocessor for stock OHLCV data."""

    def __init__(self, config: DataConfig | None = None):
        """Initialize preprocessor.

        Args:
            config: Data configuration
        """
        self.config = config
        self.min_trading_days = config.min_trading_days if config else 120
        self.recent_days = config.recent_trading_days if config else 5
        self.anomaly_threshold = config.anomaly_threshold if config else 0.30
        self.scalers: dict[str, StandardScaler] = {}

    def preprocess(
        self,
        df: pd.DataFrame,
        code: str,
        validate: bool = True,
    ) -> tuple[pd.DataFrame | None, ValidationResult]:
        """Preprocess stock data.

        Args:
            df: Raw OHLCV DataFrame
            code: Stock code
            validate: Whether to validate data

        Returns:
            Tuple of (processed DataFrame, ValidationResult)
        """
        # Handle missing values
        processed = handle_missing_values(df, method="drop")

        # Validate
        if validate:
            validation = validate_data(
                processed,
                code,
                self.min_trading_days,
                self.recent_days,
                self.anomaly_threshold,
            )
        else:
            validation = ValidationResult(
                valid=True,
                code=code,
                trading_days=len(processed),
                has_recent_trading=True,
                anomaly_dates=[],
            )

        if not validation.valid:
            return None, validation

        return processed, validation

    def preprocess_batch(
        self,
        data_dict: dict[str, pd.DataFrame],
    ) -> tuple[dict[str, pd.DataFrame], dict[str, ValidationResult]]:
        """Preprocess multiple stocks.

        Args:
            data_dict: Dictionary of {code: DataFrame}

        Returns:
            Tuple of (processed data dict, validation results dict)
        """
        processed_data = {}
        validations = {}

        for code, df in data_dict.items():
            processed, validation = self.preprocess(df, code)
            validations[code] = validation

            if processed is not None:
                processed_data[code] = processed

        valid_count = sum(1 for v in validations.values() if v.valid)
        logger.info(f"Preprocessing: {valid_count}/{len(data_dict)} passed validation")

        return processed_data, validations

    def scale_for_ttm(
        self,
        df: pd.DataFrame,
        code: str,
        columns: list[str] | None = None,
    ) -> tuple[pd.DataFrame, StandardScaler]:
        """Scale data for TTM model input.

        Args:
            df: DataFrame to scale
            code: Stock code (for storing scaler)
            columns: Columns to scale (default: close)

        Returns:
            Tuple of (scaled DataFrame, scaler)
        """
        if columns is None:
            columns = ["close"]

        scaler = StandardScaler()
        scaled = scaler.fit_transform(df, columns)
        self.scalers[code] = scaler

        return scaled, scaler

    def get_scaler(self, code: str) -> StandardScaler | None:
        """Get stored scaler for a stock.

        Args:
            code: Stock code

        Returns:
            StandardScaler or None
        """
        return self.scalers.get(code)


def prepare_model_input(
    df: pd.DataFrame,
    context_length: int,
    column: str = "close",
) -> np.ndarray:
    """Prepare input array for model prediction.

    Args:
        df: DataFrame with OHLCV data
        context_length: Number of historical points to use
        column: Column to use for prediction

    Returns:
        numpy array of shape (context_length,)
    """
    values = df[column].values

    if len(values) < context_length:
        # Pad with first value if insufficient data
        padding = np.full(context_length - len(values), values[0])
        values = np.concatenate([padding, values])

    return values[-context_length:].astype(np.float32)


def get_current_price(df: pd.DataFrame) -> float:
    """Get current (last) price from DataFrame.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        Current close price
    """
    return float(df["close"].iloc[-1])


def calculate_volume_stats(df: pd.DataFrame, days: int = 20) -> dict[str, float]:
    """Calculate volume statistics.

    Args:
        df: DataFrame with OHLCV data
        days: Number of days for averaging

    Returns:
        Dictionary with volume statistics
    """
    recent = df.tail(days)

    return {
        "avg_volume": float(recent["volume"].mean()),
        "avg_value": float((recent["close"] * recent["volume"]).mean()),
        "volume_std": float(recent["volume"].std()),
    }
