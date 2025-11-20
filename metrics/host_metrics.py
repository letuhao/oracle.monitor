"""Host Metrics - Collects system/host metrics."""
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric

class HostMetricsMetric(BaseMetric):
    def _get_display_name(self) -> str:
        return "Host Metrics"
    def _get_description(self) -> str:
        return "Host system metrics (CPU, memory, etc.)"
    def _get_category(self) -> str:
        return "system"
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        """Collect host metrics using psutil if available."""
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            process = psutil.Process()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0]
            return {
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'process_cpu_percent': process.cpu_percent(interval=0.1),
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'memory_total_gb': memory.total / (1024**3),
                'swap_percent': swap.percent,
                'load_avg': list(load_avg),
                'process_memory_mb': process.memory_info().rss / (1024**2)
            }
        except ImportError:
            return None
        except Exception as e:
            self.logger.error(f"Error collecting host metrics: {e}")
            return None
    def _get_storage_schema(self) -> Optional[str]:
        return """CREATE TABLE IF NOT EXISTS host_metrics_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT, timestamp TEXT NOT NULL,
            cpu_percent REAL, cpu_count INTEGER, process_cpu_percent REAL, memory_percent REAL,
            memory_used_gb REAL, memory_total_gb REAL, swap_percent REAL, process_memory_mb REAL)"""
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        from datetime import datetime
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute("""INSERT INTO host_metrics_history (sample_id, timestamp, cpu_percent, cpu_count, 
                       process_cpu_percent, memory_percent, memory_used_gb, memory_total_gb, swap_percent, process_memory_mb)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (sample_id or timestamp, timestamp, data.get('cpu_percent'), data.get('cpu_count'),
                      data.get('process_cpu_percent'), data.get('memory_percent'), data.get('memory_used_gb'),
                      data.get('memory_total_gb'), data.get('swap_percent'), data.get('process_memory_mb')))
        conn.commit()
        conn.close()

