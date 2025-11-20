"""Temp Usage Metric - Collects temporary tablespace usage."""
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric

class TempUsageMetric(BaseMetric):
    def _get_display_name(self) -> str:
        return "Temp Usage"
    def _get_description(self) -> str:
        return "Temporary tablespace usage by session"
    def _get_category(self) -> str:
        return "storage"
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        try:
            cursor = connection.cursor()
            query = """SELECT s.sid, s.username, s.program, t.tablespace, t.segtype, 
                       ROUND(SUM(t.blocks * 8192) / 1024 / 1024, 2) AS used_mb
                       FROM v$tempseg_usage t JOIN v$session s ON t.session_addr = s.saddr
                       GROUP BY s.sid, s.username, s.program, t.tablespace, t.segtype
                       ORDER BY used_mb DESC"""
            cursor.execute(query)
            temp_usage = [{'sid': r[0], 'username': r[1] or 'N/A', 'program': r[2] or 'N/A',
                          'tablespace': r[3], 'segtype': r[4], 'used_mb': float(r[5] or 0)} for r in cursor]
            cursor.close()
            return {'temp_usage': temp_usage, 'count': len(temp_usage)}
        except oracledb.Error as e:
            self.logger.error(f"Error collecting temp usage: {e}")
            return None
    def _get_storage_schema(self) -> Optional[str]:
        return """CREATE TABLE IF NOT EXISTS temp_usage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            sample_id TEXT, 
            timestamp TEXT NOT NULL,
            sid INTEGER, 
            username TEXT, 
            program TEXT, 
            tablespace TEXT, 
            segtype TEXT, 
            used_mb REAL
        )"""
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        from datetime import datetime
        if 'temp_usage' not in data:
            return
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        timestamp, sample_id = datetime.now().isoformat(), sample_id or datetime.now().isoformat()
        for temp in data['temp_usage']:
            cursor.execute("INSERT INTO temp_usage_history (sample_id, timestamp, sid, username, program, tablespace, segtype, used_mb) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (sample_id, timestamp, temp.get('sid'), temp.get('username'), temp.get('program'), temp.get('tablespace'), temp.get('segtype'), temp.get('used_mb')))
        conn.commit()
        conn.close()

