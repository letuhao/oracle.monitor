"""
Base Metric Class

All metrics inherit from BaseMetric to ensure consistent interface.
"""

import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import oracledb


class BaseMetric(ABC):
    """
    Base class for all metrics.
    
    Each metric is responsible for:
    1. Collecting data from Oracle
    2. Logging data to JSONL
    3. Storing data in SQLite
    4. Optional: Rendering in GUI
    """
    
    def __init__(self, log_dir: Path = Path("logs")):
        """Initialize metric with logging and storage."""
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        
        # Metric metadata (set name first, needed by logger)
        self.name = self.__class__.__name__
        self.display_name = self._get_display_name()
        self.description = self._get_description()
        self.category = self._get_category()
        self.enabled = True
        
        # Setup logger for this metric (needs self.name)
        self.logger = self._setup_logger()
    
    @abstractmethod
    def _get_display_name(self) -> str:
        """Return human-readable metric name."""
        pass
    
    @abstractmethod
    def _get_description(self) -> str:
        """Return metric description."""
        pass
    
    @abstractmethod
    def _get_category(self) -> str:
        """Return metric category (e.g., 'sessions', 'storage', 'performance')."""
        pass
    
    @abstractmethod
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        """
        Collect metric data from Oracle database.
        
        Args:
            connection: Active Oracle database connection
            **kwargs: Additional parameters for collection
            
        Returns:
            Dictionary with metric data, or None if collection failed
        """
        pass
    
    def _setup_logger(self) -> logging.Logger:
        """Setup JSONL logger for this metric."""
        log_file = self.log_dir / f"{self.name.lower()}.jsonl"
        
        logger = logging.getLogger(f"oracle_monitor_{self.name}")
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Add JSONL file handler
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        return logger
    
    def log_data(self, data: Dict, sample_id: str = None):
        """
        Log metric data to JSONL file.
        
        Args:
            data: Metric data dictionary
            sample_id: Optional sample identifier
        """
        if not data:
            return
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'metric': self.name,
            'sample_id': sample_id or datetime.now().isoformat(),
            'data': data
        }
        
        self.logger.info(json.dumps(log_entry, default=str))
    
    def init_storage(self, db_path: Path):
        """
        Initialize SQLite storage for this metric.
        
        Args:
            db_path: Path to SQLite database file
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table schema from subclass
        schema = self._get_storage_schema()
        if schema:
            cursor.execute(schema)
            
            # Create indexes if specified
            indexes = self._get_storage_indexes()
            for index_sql in indexes:
                cursor.execute(index_sql)
        
        conn.commit()
        conn.close()
    
    def store_data(self, db_path: Path, data: Dict, sample_id: str = None):
        """
        Store metric data in SQLite.
        
        Args:
            db_path: Path to SQLite database file
            data: Metric data dictionary
            sample_id: Optional sample identifier
        """
        if not data:
            return
        
        # Subclass implements actual storage logic
        self._store_data_impl(db_path, data, sample_id)
    
    def _get_storage_schema(self) -> Optional[str]:
        """
        Return CREATE TABLE SQL for this metric.
        Override in subclass if metric needs storage.
        """
        return None
    
    def _get_storage_indexes(self) -> List[str]:
        """
        Return list of CREATE INDEX SQL statements.
        Override in subclass if metric needs indexes.
        """
        return []
    
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        """
        Implement actual storage logic.
        Override in subclass if metric needs storage.
        """
        pass
    
    def render_summary(self, data: Dict) -> Optional[Dict]:
        """
        Return summary statistics for display.
        Override in subclass to provide summary view.
        
        Args:
            data: Collected metric data
            
        Returns:
            Dictionary with summary statistics for display
        """
        return None
    
    def render_details(self, data: Dict) -> Optional[Any]:
        """
        Return detailed view component.
        Override in subclass to provide detailed visualization.
        
        Args:
            data: Collected metric data
            
        Returns:
            Streamlit component or data for rendering
        """
        return None


class MetricRegistry:
    """
    Registry for dynamically discovering and managing metrics.
    """
    
    def __init__(self):
        self.metrics: Dict[str, BaseMetric] = {}
        self.categories: Dict[str, List[BaseMetric]] = {}
    
    def register(self, metric: BaseMetric):
        """Register a metric instance."""
        self.metrics[metric.name] = metric
        
        # Group by category
        category = metric.category
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(metric)
    
    def get_metric(self, name: str) -> Optional[BaseMetric]:
        """Get metric by name."""
        return self.metrics.get(name)
    
    def get_all_metrics(self) -> List[BaseMetric]:
        """Get all registered metrics."""
        return list(self.metrics.values())
    
    def get_metrics_by_category(self, category: str) -> List[BaseMetric]:
        """Get all metrics in a category."""
        return self.categories.get(category, [])
    
    def get_enabled_metrics(self) -> List[BaseMetric]:
        """Get all enabled metrics."""
        return [m for m in self.metrics.values() if m.enabled]
    
    def collect_all(self, connection: oracledb.Connection, **kwargs) -> Dict[str, Dict]:
        """
        Collect data from all enabled metrics.
        
        Args:
            connection: Active Oracle database connection
            **kwargs: Additional parameters for collection
            
        Returns:
            Dictionary mapping metric names to their data
        """
        results = {}
        
        for metric in self.get_enabled_metrics():
            try:
                data = metric.collect(connection, **kwargs)
                if data:
                    results[metric.name] = data
            except Exception as e:
                logging.error(f"Error collecting {metric.name}: {e}")
        
        return results
    
    def log_all(self, data: Dict[str, Dict], sample_id: str = None):
        """Log data for all metrics."""
        for metric_name, metric_data in data.items():
            metric = self.get_metric(metric_name)
            if metric and metric_data:
                metric.log_data(metric_data, sample_id)
    
    def store_all(self, db_path: Path, data: Dict[str, Dict], sample_id: str = None):
        """Store data for all metrics."""
        for metric_name, metric_data in data.items():
            metric = self.get_metric(metric_name)
            if metric and metric_data:
                metric.store_data(db_path, metric_data, sample_id)

