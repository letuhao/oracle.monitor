"""IO Sessions Metric - Collects session I/O statistics."""
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric

class IOSessionsMetric(BaseMetric):
    def _get_display_name(self) -> str:
        return "I/O Sessions"
    def _get_description(self) -> str:
        return "Session-level I/O statistics"
    def _get_category(self) -> str:
        return "performance"
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        limit = kwargs.get('limit', 20)
        try:
            cursor = connection.cursor()
            query = """SELECT s.sid, s.username, s.program, s.status, s.sql_id,
                       ROUND(i.block_gets + i.consistent_gets / 1024 / 128, 2) AS read_mb,
                       ROUND(i.physical_writes / 1024 / 128, 2) AS write_mb
                       FROM v$session s JOIN v$sess_io i ON s.sid = i.sid
                       WHERE s.username IS NOT NULL
                       ORDER BY (i.block_gets + i.consistent_gets) DESC FETCH FIRST :limit ROWS ONLY"""
            cursor.execute(query, {'limit': limit})
            sessions = [{'sid': r[0], 'username': r[1] or 'N/A', 'program': r[2] or 'N/A', 'status': r[3],
                        'sql_id': r[4] or 'N/A', 'read_mb': float(r[5] or 0), 'write_mb': float(r[6] or 0)} for r in cursor]
            cursor.close()
            return {'io_sessions': sessions, 'count': len(sessions)}
        except oracledb.Error as e:
            self.logger.error(f"Error collecting IO sessions: {e}")
            return None
    def _get_storage_schema(self) -> Optional[str]:
        return """CREATE TABLE IF NOT EXISTS io_sessions_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT, timestamp TEXT NOT NULL,
            sid INTEGER, username TEXT, program TEXT, status TEXT, sql_id TEXT, read_mb REAL, write_mb REAL)"""
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        from datetime import datetime
        if 'io_sessions' not in data:
            return
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        timestamp, sample_id = datetime.now().isoformat(), sample_id or datetime.now().isoformat()
        for session in data['io_sessions']:
            cursor.execute("""INSERT INTO io_sessions_history (sample_id, timestamp, sid, username, program, status, sql_id, read_mb, write_mb)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                         (sample_id, timestamp, session.get('sid'), session.get('username'), session.get('program'),
                          session.get('status'), session.get('sql_id'), session.get('read_mb'), session.get('write_mb')))
        conn.commit()
        conn.close()

