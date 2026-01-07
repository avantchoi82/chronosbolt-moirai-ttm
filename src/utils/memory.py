"""Memory management utilities for GPU/CPU resources."""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("ensemble")


@dataclass
class MemoryInfo:
    """Memory usage information."""
    gpu_allocated: float = 0.0  # GB
    gpu_reserved: float = 0.0   # GB
    gpu_total: float = 0.0      # GB
    ram_used: float = 0.0       # GB
    ram_available: float = 0.0  # GB
    cuda_available: bool = False


def get_memory_info() -> MemoryInfo:
    """Get current memory usage information.

    Returns:
        MemoryInfo dataclass with memory statistics
    """
    info = MemoryInfo()

    # GPU memory (if available)
    try:
        import torch
        if torch.cuda.is_available():
            info.cuda_available = True
            info.gpu_allocated = torch.cuda.memory_allocated() / 1024**3
            info.gpu_reserved = torch.cuda.memory_reserved() / 1024**3
            info.gpu_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    except ImportError:
        pass

    # RAM memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        info.ram_used = mem.used / 1024**3
        info.ram_available = mem.available / 1024**3
    except ImportError:
        pass

    return info


def get_gpu_memory() -> tuple[float, float, float]:
    """Get GPU memory usage.

    Returns:
        Tuple of (allocated, reserved, total) in GB
    """
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            return allocated, reserved, total
    except ImportError:
        pass
    return 0.0, 0.0, 0.0


def check_available_memory(required_gb: float = 1.0) -> bool:
    """Check if sufficient GPU memory is available.

    Args:
        required_gb: Required memory in GB

    Returns:
        True if sufficient memory available
    """
    try:
        import torch
        if torch.cuda.is_available():
            allocated, _, total = get_gpu_memory()
            available = total - allocated
            return available >= required_gb
    except ImportError:
        pass
    return True  # If no GPU, assume CPU mode is fine


def clear_memory() -> None:
    """Clear Python garbage and CUDA cache."""
    # Python garbage collection
    gc.collect()

    # CUDA memory cleanup
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except ImportError:
        pass


def unload_model(model: Any, model_name: str = "model") -> None:
    """Safely unload a model and free memory.

    Follows CONSTITUTION.md 제13조 memory management requirements:
    1. Delete model object
    2. Python garbage collection
    3. Clear CUDA cache
    4. CUDA synchronization

    Args:
        model: Model object to unload
        model_name: Name for logging
    """
    logger.debug(f"Unloading {model_name}...")

    # Step 1: Delete model reference
    if model is not None:
        del model

    # Step 2: Python garbage collection
    gc.collect()

    # Step 3 & 4: CUDA cleanup
    try:
        import torch
        if torch.cuda.is_available():
            # Clear CUDA cache
            torch.cuda.empty_cache()
            # Synchronize
            torch.cuda.synchronize()
    except ImportError:
        pass

    # Log memory after cleanup
    info = get_memory_info()
    if info.cuda_available:
        logger.debug(
            f"Memory after unload: {info.gpu_allocated:.2f}GB allocated, "
            f"{info.gpu_reserved:.2f}GB reserved"
        )


class MemoryTracker:
    """Context manager for tracking memory usage during operations."""

    def __init__(self, operation_name: str = "operation"):
        self.operation_name = operation_name
        self.start_info: MemoryInfo | None = None
        self.end_info: MemoryInfo | None = None

    def __enter__(self) -> "MemoryTracker":
        self.start_info = get_memory_info()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.end_info = get_memory_info()
        self._log_diff()
        return False

    def _log_diff(self) -> None:
        """Log memory usage difference."""
        if self.start_info and self.end_info:
            gpu_diff = self.end_info.gpu_allocated - self.start_info.gpu_allocated
            ram_diff = self.end_info.ram_used - self.start_info.ram_used

            msg = f"Memory change for {self.operation_name}: "
            if self.end_info.cuda_available:
                msg += f"GPU: {gpu_diff:+.2f}GB, "
            msg += f"RAM: {ram_diff:+.2f}GB"
            logger.debug(msg)

    @property
    def gpu_delta(self) -> float:
        """Get GPU memory change in GB."""
        if self.start_info and self.end_info:
            return self.end_info.gpu_allocated - self.start_info.gpu_allocated
        return 0.0

    @property
    def ram_delta(self) -> float:
        """Get RAM change in GB."""
        if self.start_info and self.end_info:
            return self.end_info.ram_used - self.start_info.ram_used
        return 0.0


def ensure_memory(required_gb: float = 0.5, max_retries: int = 3) -> bool:
    """Ensure sufficient GPU memory is available, with cleanup retries.

    Args:
        required_gb: Required memory in GB
        max_retries: Maximum cleanup attempts

    Returns:
        True if memory is available after cleanup
    """
    for attempt in range(max_retries):
        if check_available_memory(required_gb):
            return True

        logger.warning(
            f"Insufficient memory (attempt {attempt + 1}/{max_retries}), "
            f"cleaning up..."
        )
        clear_memory()

    return check_available_memory(required_gb)
