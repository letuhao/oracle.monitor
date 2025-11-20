"""
Session Overview Metric

Collects overall session statistics including:
- Total sessions
- Active/Inactive sessions
- Blocked sessions
- Logical/Physical reads
- CPU usage
"""

import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric


class SessionOverviewMetric(BaseMetric):
    """Collects session overview statistics."""
    
    def _get_display_name(self) -> str:
        return "Session Overview"
    
    def _get_description(self) -> str:
        return "Overall session statistics including counts, reads, and CPU usage"
    
    def _get_category(self) -> str:
        return "sessions"
    
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        """Collect session overview data."""
        try:
            cursor = connection.cursor()
            
            # Get statistic IDs
            stat_logical = self._get_statistic_id(cursor, 'session logical reads')
            stat_physical = self._get_statistic_id(cursor, 'physical reads')
            stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')
            
            if not all([stat_logical, stat_physical, stat_cpu]):
                return None
            
            # Main query
            query = """
                SELECT 
                    COUNT(*) AS total_sessions,
                    COUNT(CASE WHEN s.status = 'ACTIVE' THEN 1 END) AS active_sessions,
                    COUNT(CASE WHEN s.status = 'INACTIVE' THEN 1 END) AS inactive_sessions,
                    COUNT(CASE WHEN s.blocking_session IS NOT NULL THEN 1 END) AS blocked_sessions,
                    ROUND(SUM(CASE WHEN stat.statistic# = :stat_logical THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS total_logical_reads_mb,
                    ROUND(SUM(CASE WHEN stat.statistic# = :stat_physical THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS total_physical_reads_mb,
                    ROUND(SUM(CASE WHEN stat.statistic# = :stat_cpu THEN stat.value ELSE 0 END) / 100, 2) AS total_cpu_seconds
                FROM v$session s
                LEFT JOIN v$sesstat stat ON s.sid = stat.sid 
                    AND stat.statistic# IN (:stat_logical, :stat_physical, :stat_cpu)
                WHERE s.username IS NOT NULL
            """
            
            cursor.execute(query, {
                'stat_logical': stat_logical,
                'stat_physical': stat_physical,
                'stat_cpu': stat_cpu
            })
            
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                return {
                    'total_sessions': row[0] or 0,
                    'active_sessions': row[1] or 0,
                    'inactive_sessions': row[2] or 0,
                    'blocked_sessions': row[3] or 0,
                    'logical_reads_mb': float(row[4] or 0),
                    'physical_reads_mb': float(row[5] or 0),
                    'cpu_seconds': float(row[6] or 0)
                }
            return None
            
        except oracledb.Error as e:
            self.logger.error(f"Error collecting session overview: {e}")
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
            CREATE TABLE IF NOT EXISTS session_overview_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                total_sessions INTEGER,
                active_sessions INTEGER,
                inactive_sessions INTEGER,
                blocked_sessions INTEGER,
                logical_reads_mb REAL,
                physical_reads_mb REAL,
                cpu_seconds REAL
            )
        """
    
    def _get_storage_indexes(self) -> list:
        """Return CREATE INDEX SQL statements."""
        return [
            "CREATE INDEX IF NOT EXISTS idx_session_overview_ts ON session_overview_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_session_overview_sample ON session_overview_history(sample_id)"
        ]
    
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        """Store data in SQLite."""
        from datetime import datetime
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO session_overview_history (
                sample_id, timestamp, total_sessions, active_sessions, 
                inactive_sessions, blocked_sessions, logical_reads_mb, 
                physical_reads_mb, cpu_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sample_id or datetime.now().isoformat(),
            datetime.now().isoformat(),
            data.get('total_sessions'),
            data.get('active_sessions'),
            data.get('inactive_sessions'),
            data.get('blocked_sessions'),
            data.get('logical_reads_mb'),
            data.get('physical_reads_mb'),
            data.get('cpu_seconds')
        ))
        
        conn.commit()
        conn.close()
    
    def render_summary(self, data: Dict) -> Optional[Dict]:
        """Return summary statistics for display."""
        return {
            'Total Sessions': data.get('total_sessions', 0),
            'Active': data.get('active_sessions', 0),
            'Inactive': data.get('inactive_sessions', 0),
            'Blocked': data.get('blocked_sessions', 0),
            'CPU (sec)': f"{data.get('cpu_seconds', 0):.1f}",
            'Logical Reads (MB)': f"{data.get('logical_reads_mb', 0):.1f}"
        }

