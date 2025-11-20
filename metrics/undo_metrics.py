"""Undo Metrics - Collects undo tablespace metrics."""
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric

class UndoMetricsMetric(BaseMetric):
    def _get_display_name(self) -> str:
        return "Undo Metrics"
    def _get_description(self) -> str:
        return "Undo tablespace and transaction metrics"
    def _get_category(self) -> str:
        return "storage"
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        try:
            cursor = connection.cursor()
            query = """SELECT (SELECT value FROM v$parameter WHERE name = 'undo_retention') AS undo_retention,
                       (SELECT COUNT(*) FROM v$transaction) AS active_transactions,
                       (SELECT SUM(bytes)/1024/1024 FROM dba_undo_extents WHERE status = 'ACTIVE') AS undo_mb_active,
                       (SELECT SUM(bytes)/1024/1024 FROM dba_undo_extents) AS undo_mb_total FROM dual"""
            cursor.execute(query)
            row = cursor.fetchone()
            cursor.close()
            return {'undo_retention': int(row[0] or 0), 'active_transactions': int(row[1] or 0),
                   'undo_mb_active': float(row[2] or 0), 'undo_mb_total': float(row[3] or 0)}
        except oracledb.Error as e:
            self.logger.error(f"Error collecting undo metrics: {e}")
            return None
    def _get_storage_schema(self) -> Optional[str]:
        return """CREATE TABLE IF NOT EXISTS undo_metrics_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT, timestamp TEXT NOT NULL,
            undo_retention INTEGER, active_transactions INTEGER, undo_mb_active REAL, undo_mb_total REAL)"""
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        from datetime import datetime
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute("INSERT INTO undo_metrics_history (sample_id, timestamp, undo_retention, active_transactions, undo_mb_active, undo_mb_total) VALUES (?, ?, ?, ?, ?, ?)",
                     (sample_id or timestamp, timestamp, data.get('undo_retention'), data.get('active_transactions'), data.get('undo_mb_active'), data.get('undo_mb_total')))
        conn.commit()
        conn.close()

