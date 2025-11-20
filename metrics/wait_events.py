"""Wait Events Metric - Collects database wait event statistics."""
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric

class WaitEventsMetric(BaseMetric):
    def _get_display_name(self) -> str:
        return "Wait Events"
    def _get_description(self) -> str:
        return "Top database wait events"
    def _get_category(self) -> str:
        return "performance"
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        """Collect wait events data."""
        limit = kwargs.get('limit', 20)
        try:
            cursor = connection.cursor()
            query = """
                SELECT event, total_waits, time_waited / 100 AS total_wait_seconds,
                       CASE WHEN total_waits > 0 THEN time_waited / total_waits / 1000 ELSE 0 END AS avg_wait_ms
                FROM v$system_event
                WHERE wait_class != 'Idle'
                ORDER BY time_waited DESC
                FETCH FIRST :limit ROWS ONLY
            """
            cursor.execute(query, {'limit': limit})
            events = [{'event': r[0], 'total_waits': r[1], 'total_wait_seconds': float(r[2] or 0), 
                      'avg_wait_ms': float(r[3] or 0)} for r in cursor]
            cursor.close()
            return {'wait_events': events, 'count': len(events)}
        except oracledb.Error as e:
            self.logger.error(f"Error collecting wait events: {e}")
            return None
    def _get_storage_schema(self) -> Optional[str]:
        return """CREATE TABLE IF NOT EXISTS wait_events_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT, timestamp TEXT NOT NULL,
            event TEXT, total_waits INTEGER, total_wait_seconds REAL, avg_wait_ms REAL)"""
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        from datetime import datetime
        if 'wait_events' not in data:
            return
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        timestamp, sample_id = datetime.now().isoformat(), sample_id or datetime.now().isoformat()
        for event in data['wait_events']:
            cursor.execute("INSERT INTO wait_events_history (sample_id, timestamp, event, total_waits, total_wait_seconds, avg_wait_ms) VALUES (?, ?, ?, ?, ?, ?)",
                         (sample_id, timestamp, event.get('event'), event.get('total_waits'), event.get('total_wait_seconds'), event.get('avg_wait_ms')))
        conn.commit()
        conn.close()

