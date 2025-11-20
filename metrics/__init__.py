"""
Oracle Monitor Metrics Package

This package contains modular, self-contained metric collectors.
Each metric handles its own:
- Data collection from Oracle
- Logging (JSONL)
- SQLite persistence
- Optional GUI rendering

New metrics are automatically discovered and registered.
"""

from .base_metric import BaseMetric, MetricRegistry
from .registry import get_registry

__all__ = ['BaseMetric', 'MetricRegistry', 'get_registry']

