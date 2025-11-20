"""Resource Limits Metric - Collects database resource limits."""
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric

class ResourceLimitsMetric(BaseMetric):
    def _get_display_name(self) -> str:
        return "Resource Limits"
    def _get_description(self) -> str:
        return "Database resource usage vs limits"
    def _get_category(self) -> str:
        return "system"
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        try:
            cursor = connection.cursor()
            query = """SELECT resource_name, current_utilization, max_utilization, limit_value
                       FROM v$resource_limit WHERE resource_name IN ('processes', 'sessions')"""
            cursor.execute(query)
            limits = {}
            for row in cursor:
                limits[row[0].lower()] = {
                    'current': int(row[1] or 0),
                    'max': int(row[2] or 0),
                    'limit': str(row[3])
                }
            cursor.close()
            return {'limits': limits}
        except oracledb.Error as e:
            self.logger.error(f"Error collecting resource limits: {e}")
            return None
    def _get_storage_schema(self) -> Optional[str]:
        return """CREATE TABLE IF NOT EXISTS resource_limits_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT, timestamp TEXT NOT NULL,
            resource_name TEXT, current_utilization INTEGER, max_utilization INTEGER, limit_value TEXT)"""
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        from datetime import datetime
        if 'limits' not in data:
            return
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        timestamp, sample_id = datetime.now().isoformat(), sample_id or datetime.now().isoformat()
        for resource_name, limit in data['limits'].items():
            cursor.execute("""INSERT INTO resource_limits_history (sample_id, timestamp, resource_name, 
                           current_utilization, max_utilization, limit_value) VALUES (?, ?, ?, ?, ?, ?)""",
                         (sample_id, timestamp, resource_name, limit.get('current'), limit.get('max'), limit.get('limit')))
        conn.commit()
        conn.close()

