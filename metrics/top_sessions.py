"""
Top Sessions Metric

Collects information about top resource-consuming sessions.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import oracledb
from .base_metric import BaseMetric


class TopSessionsMetric(BaseMetric):
    """Collects top resource-consuming sessions."""
    
    def _get_display_name(self) -> str:
        return "Top Sessions"
    
    def _get_description(self) -> str:
        return "Top resource-consuming sessions by logical reads and CPU"
    
    def _get_category(self) -> str:
        return "sessions"
    
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        """Collect top sessions data."""
        limit = kwargs.get('limit', 20)
        
        try:
            cursor = connection.cursor()
            
            # Get statistic IDs
            stat_logical = self._get_statistic_id(cursor, 'session logical reads')
            stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')
            
            if not all([stat_logical, stat_cpu]):
                return None
            
            query = """
                SELECT 
                    s.sid,
                    s.serial#,
                    s.username,
                    s.program,
                    s.status,
                    ROUND(MAX(CASE WHEN stat.statistic# = :stat_logical THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS logical_reads_mb,
                    ROUND(MAX(CASE WHEN stat.statistic# = :stat_cpu THEN stat.value ELSE 0 END) / 100, 2) AS cpu_seconds,
                    s.event,
                    s.sql_id,
                    s.machine,
                    s.module
                FROM v$session s
                LEFT JOIN v$sesstat stat ON s.sid = stat.sid 
                    AND stat.statistic# IN (:stat_logical, :stat_cpu)
                WHERE s.username IS NOT NULL
                GROUP BY s.sid, s.serial#, s.username, s.program, s.status, s.event, s.sql_id, s.machine, s.module
                ORDER BY MAX(CASE WHEN stat.statistic# = :stat_logical THEN stat.value ELSE 0 END) DESC
                FETCH FIRST :limit ROWS ONLY
            """
            
            cursor.execute(query, {
                'stat_logical': stat_logical,
                'stat_cpu': stat_cpu,
                'limit': limit
            })
            
            sessions = []
            for row in cursor:
                sessions.append({
                    'sid': row[0],
                    'serial': row[1],
                    'username': row[2] or 'N/A',
                    'program': row[3] or 'N/A',
                    'status': row[4] or 'N/A',
                    'logical_reads_mb': float(row[5] or 0),
                    'cpu_seconds': float(row[6] or 0),
                    'event': row[7] or 'N/A',
                    'sql_id': row[8] or 'N/A',
                    'machine': row[9] or 'N/A',
                    'module': row[10] or 'N/A'
                })
            
            cursor.close()
            return {'sessions': sessions, 'count': len(sessions)}
            
        except oracledb.Error as e:
            self.logger.error(f"Error collecting top sessions: {e}")
            return None
    
    def _get_statistic_id(self, cursor: oracledb.Cursor, stat_name: str) -> Optional[int]:
        """Get statistic ID from v$statname."""
        try:
            cursor.execute(
                "SELECT statistic# FROM v$statname WHERE name = :name",
                name=stat_name
            )
            result = cursor.fetchone()
            return result[0] if result else None
        except oracledb.Error:
            return None
    
    def _get_storage_schema(self) -> Optional[str]:
        """Return CREATE TABLE SQL."""
        return """
            CREATE TABLE IF NOT EXISTS top_sessions_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                sid INTEGER,
                serial INTEGER,
                username TEXT,
                program TEXT,
                status TEXT,
                logical_reads_mb REAL,
                cpu_seconds REAL,
                event TEXT,
                sql_id TEXT,
                machine TEXT,
                module TEXT
            )
        """
    
    def _get_storage_indexes(self) -> List[str]:
        """Return CREATE INDEX SQL statements."""
        return [
            "CREATE INDEX IF NOT EXISTS idx_top_sessions_ts ON top_sessions_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_top_sessions_sid ON top_sessions_history(sid)"
        ]
    
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        """Store data in SQLite."""
        from datetime import datetime
        
        if 'sessions' not in data:
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        sample_id = sample_id or timestamp
        
        for session in data['sessions']:
            cursor.execute("""
                INSERT INTO top_sessions_history (
                    sample_id, timestamp, sid, serial, username, program, 
                    status, logical_reads_mb, cpu_seconds, event, sql_id, 
                    machine, module
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sample_id, timestamp,
                session.get('sid'),
                session.get('serial'),
                session.get('username'),
                session.get('program'),
                session.get('status'),
                session.get('logical_reads_mb'),
                session.get('cpu_seconds'),
                session.get('event'),
                session.get('sql_id'),
                session.get('machine'),
                session.get('module')
            ))
        
        conn.commit()
        conn.close()

