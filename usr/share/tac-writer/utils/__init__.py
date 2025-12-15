"""
TAC Utils Package
Utility functions and helper classes for the TAC application
"""

from .helpers import (
    FileHelper,
    TextHelper, 
    ValidationHelper,
    FormatHelper,
    DebugHelper
)
from .i18n import _

# Import version from config to avoid duplication
try:
    from core.config import Config
    __version__ = Config.APP_VERSION
except ImportError:
    __version__ = 'unknown'

__all__ = [
    'FileHelper',
    'TextHelper',
    'ValidationHelper', 
    'FormatHelper',
    'DebugHelper',
    '_'
]