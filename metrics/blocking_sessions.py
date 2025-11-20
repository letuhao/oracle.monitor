"""
Blocking Sessions Metric

Collects information about blocked sessions and their blockers.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import oracledb
from .base_metric import BaseMetric


class BlockingSessionsMetric(BaseMetric):
    """Collects blocking sessions information."""
    
    def _get_display_name(self) -> str:
        return "Blocking Sessions"
    
    def _get_description(self) -> str:
        return "Sessions that are blocking other sessions"
    
    def _get_category(self) -> str:
        return "sessions"
    
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        """Collect blocking sessions data."""
        try:
            cursor = connection.cursor()
            
            query = """
                SELECT 
                    blocking.sid AS blocking_sid,
                    blocking.serial# AS blocking_serial,
                    blocking.username AS blocking_user,
                    blocking.program AS blocking_program,
                    blocked.sid AS blocked_sid,
                    blocked.serial# AS blocked_serial,
                    blocked.username AS blocked_user,
                    blocked.program AS blocked_program,
                    blocked.event AS wait_event,
                    blocked.seconds_in_wait AS wait_seconds
                FROM v$session blocking
                JOIN v$session blocked ON blocking.sid = blocked.blocking_session
                WHERE blocking.username IS NOT NULL
                ORDER BY blocked.seconds_in_wait DESC
            """
            
            cursor.execute(query)
            
            blocking_info = []
            for row in cursor:
                blocking_info.append({
                    'blocking_sid': row[0],
                    'blocking_serial': row[1],
                    'blocking_user': row[2] or 'N/A',
                    'blocking_program': row[3] or 'N/A',
                    'blocked_sid': row[4],
                    'blocked_serial': row[5],
                    'blocked_user': row[6] or 'N/A',
                    'blocked_program': row[7] or 'N/A',
                    'wait_event': row[8] or 'N/A',
                    'wait_seconds': row[9] or 0
                })
            
            cursor.close()
            return {'blocking_sessions': blocking_info, 'count': len(blocking_info)}
            
        except oracledb.Error as e:
            self.logger.error(f"Error collecting blocking sessions: {e}")
            return None
    
    def _get_storage_schema(self) -> Optional[str]:
        """Return CREATE TABLE SQL."""
        return """
            CREATE TABLE IF NOT EXISTS blocking_sessions_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                blocking_sid INTEGER,
                blocking_serial INTEGER,
                blocking_user TEXT,
                blocking_program TEXT,
                blocked_sid INTEGER,
                blocked_serial INTEGER,
                blocked_user TEXT,
                blocked_program TEXT,
                wait_event TEXT,
                wait_seconds REAL
            )
        """
    
    def _get_storage_indexes(self) -> List[str]:
        """Return CREATE INDEX SQL statements."""
        return [
            "CREATE INDEX IF NOT EXISTS idx_blocking_ts ON blocking_sessions_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_blocking_sid ON blocking_sessions_history(blocking_sid)"
        ]
    
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        """Store data in SQLite."""
        from datetime import datetime
        
        if 'blocking_sessions' not in data:
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        sample_id = sample_id or timestamp
        
        for block in data['blocking_sessions']:
            cursor.execute("""
                INSERT INTO blocking_sessions_history (
                    sample_id, timestamp, blocking_sid, blocking_serial, 
                    blocking_user, blocking_program, blocked_sid, blocked_serial,
                    blocked_user, blocked_program, wait_event, wait_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sample_id, timestamp,
                block.get('blocking_sid'),
                block.get('blocking_serial'),
                block.get('blocking_user'),
                block.get('blocking_program'),
                block.get('blocked_sid'),
                block.get('blocked_serial'),
                block.get('blocked_user'),
                block.get('blocked_program'),
                block.get('wait_event'),
                block.get('wait_seconds')
            ))
        
        conn.commit()
        conn.close()

