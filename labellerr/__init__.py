"""Labellerr SDK - Python client for Labellerr API."""

from .async_client import AsyncLabellerrClient
from .client import LabellerrClient
from .exceptions import LabellerrError

# Get version from package metadata
try:
    from importlib.metadata import version

    __version__ = version("labellerr-sdk")
except ImportError:
    # Python < 3.8
    from importlib_metadata import version

    __version__ = version("labellerr-sdk")
except Exception:
    __version__ = "unknown"

__all__ = [
    "__version__",
    "LabellerrClient",
    "AsyncLabellerrClient",
    "LabellerrError",
]
