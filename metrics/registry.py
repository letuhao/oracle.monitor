"""
Metric Registry - Auto-discovery and management of metrics
"""

from pathlib import Path
from .base_metric import MetricRegistry

# Global registry instance
_registry = None


def get_registry(log_dir: Path = Path("logs")) -> MetricRegistry:
    """
    Get or create the global metric registry.
    
    Args:
        log_dir: Directory for log files
        
    Returns:
        MetricRegistry instance with all metrics registered
    """
    global _registry
    
    if _registry is None:
        _registry = MetricRegistry()
        _auto_discover_metrics(log_dir)
    
    return _registry


def _auto_discover_metrics(log_dir: Path):
    """
    Auto-discover and register all metric modules.
    
    Scans the metrics package for classes inheriting from BaseMetric
    and automatically registers them.
    """
    from . import session_overview
    from . import top_sessions
    from . import blocking_sessions
    from . import tablespace_usage
    from . import wait_events
    from . import temp_usage
    from . import undo_metrics
    from . import redo_metrics
    from . import plan_churn
    from . import io_sessions
    from . import host_metrics
    from . import resource_limits
    
    # Instantiate and register each metric
    metrics = [
        session_overview.SessionOverviewMetric(log_dir),
        top_sessions.TopSessionsMetric(log_dir),
        blocking_sessions.BlockingSessionsMetric(log_dir),
        tablespace_usage.TablespaceUsageMetric(log_dir),
        wait_events.WaitEventsMetric(log_dir),
        temp_usage.TempUsageMetric(log_dir),
        undo_metrics.UndoMetricsMetric(log_dir),
        redo_metrics.RedoMetricsMetric(log_dir),
        plan_churn.PlanChurnMetric(log_dir),
        io_sessions.IOSessionsMetric(log_dir),
        host_metrics.HostMetricsMetric(log_dir),
        resource_limits.ResourceLimitsMetric(log_dir),
    ]
    
    for metric in metrics:
        _registry.register(metric)


def reset_registry():
    """Reset the global registry (useful for testing)."""
    global _registry
    _registry = None

