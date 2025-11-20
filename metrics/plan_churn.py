"""Plan Churn Metric - Collects SQL plan change metrics."""
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric

class PlanChurnMetric(BaseMetric):
    def _get_display_name(self) -> str:
        return "Plan Churn"
    def _get_description(self) -> str:
        return "SQL statements with multiple execution plans"
    def _get_category(self) -> str:
        return "performance"
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        limit = kwargs.get('limit', 20)
        try:
            cursor = connection.cursor()
            query = """SELECT sql_id, plan_hash_value, executions, elapsed_time/1000000 AS elapsed_seconds,
                       buffer_gets, disk_reads, rows_processed, last_active_time
                       FROM v$sql WHERE executions > 0 ORDER BY executions DESC FETCH FIRST :limit ROWS ONLY"""
            cursor.execute(query, {'limit': limit})
            plans = [{'sql_id': r[0], 'plan_hash_value': r[1], 'executions': r[2], 'elapsed_seconds': float(r[3] or 0),
                     'buffer_gets': r[4], 'disk_reads': r[5], 'rows_processed': r[6], 'last_active_time': str(r[7])} for r in cursor]
            cursor.close()
            return {'plans': plans, 'count': len(plans)}
        except oracledb.Error as e:
            self.logger.error(f"Error collecting plan churn: {e}")
            return None
    def _get_storage_schema(self) -> Optional[str]:
        return """CREATE TABLE IF NOT EXISTS plan_churn_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT, timestamp TEXT NOT NULL,
            sql_id TEXT, plan_hash_value INTEGER, executions INTEGER, elapsed_seconds REAL,
            buffer_gets INTEGER, disk_reads INTEGER, rows_processed INTEGER, last_active_time TEXT)"""
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        from datetime import datetime
        if 'plans' not in data:
            return
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        timestamp, sample_id = datetime.now().isoformat(), sample_id or datetime.now().isoformat()
        for plan in data['plans']:
            cursor.execute("""INSERT INTO plan_churn_history (sample_id, timestamp, sql_id, plan_hash_value, 
                           executions, elapsed_seconds, buffer_gets, disk_reads, rows_processed, last_active_time)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                         (sample_id, timestamp, plan.get('sql_id'), plan.get('plan_hash_value'), plan.get('executions'),
                          plan.get('elapsed_seconds'), plan.get('buffer_gets'), plan.get('disk_reads'), 
                          plan.get('rows_processed'), plan.get('last_active_time')))
        conn.commit()
        conn.close()

