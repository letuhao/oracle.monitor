"""Redo Metrics - Collects redo log metrics."""
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric

class RedoMetricsMetric(BaseMetric):
    def _get_display_name(self) -> str:
        return "Redo Metrics"
    def _get_description(self) -> str:
        return "Redo log generation and performance metrics"
    def _get_category(self) -> str:
        return "performance"
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        try:
            cursor = connection.cursor()
            query = """SELECT name, value FROM v$sysstat 
                       WHERE name IN ('redo size', 'redo writes', 'redo write time')"""
            cursor.execute(query)
            metrics = {row[0]: float(row[1]) for row in cursor}
            cursor.close()
            return {'redo_size': metrics.get('redo size', 0), 'redo_writes': metrics.get('redo writes', 0),
                   'redo_write_time': metrics.get('redo write time', 0)}
        except oracledb.Error as e:
            self.logger.error(f"Error collecting redo metrics: {e}")
            return None
    def _get_storage_schema(self) -> Optional[str]:
        return """CREATE TABLE IF NOT EXISTS redo_metrics_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT, timestamp TEXT NOT NULL,
            redo_size REAL, redo_writes REAL, redo_write_time REAL)"""
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        from datetime import datetime
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute("INSERT INTO redo_metrics_history (sample_id, timestamp, redo_size, redo_writes, redo_write_time) VALUES (?, ?, ?, ?, ?)",
                     (sample_id or timestamp, timestamp, data.get('redo_size'), data.get('redo_writes'), data.get('redo_write_time')))
        conn.commit()
        conn.close()

