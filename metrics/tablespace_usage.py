"""
Tablespace Usage Metric

Collects tablespace usage statistics.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import oracledb
from .base_metric import BaseMetric


class TablespaceUsageMetric(BaseMetric):
    """Collects tablespace usage information."""
    
    def _get_display_name(self) -> str:
        return "Tablespace Usage"
    
    def _get_description(self) -> str:
        return "Disk space usage by tablespace"
    
    def _get_category(self) -> str:
        return "storage"
    
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        """Collect tablespace usage data."""
        try:
            cursor = connection.cursor()
            
            query = """
                SELECT 
                    ts.tablespace_name,
                    ts.contents AS type,
                    ts.status,
                    NVL(df.used_mb, 0) AS used_mb,
                    NVL(df.allocated_mb, 0) AS allocated_mb,
                    NVL(df.max_mb, 0) AS max_mb,
                    NVL(df.allocated_mb - df.used_mb, 0) AS free_mb,
                    CASE 
                        WHEN NVL(df.allocated_mb, 0) > 0 THEN 
                            ROUND((NVL(df.used_mb, 0) / df.allocated_mb) * 100, 2)
                        ELSE 0 
                    END AS pct_used,
                    NVL(df.max_mb - df.allocated_mb, 0) AS autoextend_headroom_mb,
                    NVL(df.file_count, 0) AS files,
                    NVL(df.autoextend_count, 0) AS autoextend_files,
                    CASE WHEN NVL(df.autoextend_count, 0) > 0 THEN 1 ELSE 0 END AS autoextend_capable
                FROM dba_tablespaces ts
                LEFT JOIN (
                    SELECT 
                        tablespace_name,
                        ROUND(SUM(bytes) / 1024 / 1024, 2) AS allocated_mb,
                        ROUND(SUM(CASE WHEN maxbytes = 0 THEN bytes ELSE maxbytes END) / 1024 / 1024, 2) AS max_mb,
                        COUNT(*) AS file_count,
                        SUM(CASE WHEN maxbytes > bytes THEN 1 ELSE 0 END) AS autoextend_count,
                        ROUND(SUM(bytes - NVL((SELECT SUM(bytes) FROM dba_free_space WHERE tablespace_name = df.tablespace_name), 0)) / 1024 / 1024, 2) AS used_mb
                    FROM dba_data_files df
                    GROUP BY tablespace_name
                ) df ON ts.tablespace_name = df.tablespace_name
                WHERE ts.contents != 'UNDO'
                ORDER BY pct_used DESC
            """
            
            cursor.execute(query)
            
            tablespaces = []
            for row in cursor:
                tablespaces.append({
                    'tablespace': row[0],
                    'type': row[1],
                    'status': row[2],
                    'used_mb': float(row[3] or 0),
                    'allocated_mb': float(row[4] or 0),
                    'max_mb': float(row[5] or 0),
                    'free_mb': float(row[6] or 0),
                    'pct_used': float(row[7] or 0),
                    'autoextend_headroom_mb': float(row[8] or 0),
                    'files': int(row[9] or 0),
                    'autoextend_files': int(row[10] or 0),
                    'autoextend_capable': int(row[11] or 0)
                })
            
            cursor.close()
            return {'tablespaces': tablespaces, 'count': len(tablespaces)}
            
        except oracledb.Error as e:
            self.logger.error(f"Error collecting tablespace usage: {e}")
            return None
    
    def _get_storage_schema(self) -> Optional[str]:
        """Return CREATE TABLE SQL."""
        return """
            CREATE TABLE IF NOT EXISTS tablespace_usage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                tablespace TEXT,
                type TEXT,
                status TEXT,
                used_mb REAL,
                allocated_mb REAL,
                max_mb REAL,
                free_mb REAL,
                pct_used REAL,
                autoextend_headroom_mb REAL,
                files INTEGER,
                autoextend_files INTEGER,
                autoextend_capable INTEGER
            )
        """
    
    def _get_storage_indexes(self) -> List[str]:
        """Return CREATE INDEX SQL statements."""
        return [
            "CREATE INDEX IF NOT EXISTS idx_tablespace_ts ON tablespace_usage_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_tablespace_name ON tablespace_usage_history(tablespace)"
        ]
    
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        """Store data in SQLite."""
        from datetime import datetime
        
        if 'tablespaces' not in data:
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        sample_id = sample_id or timestamp
        
        for ts in data['tablespaces']:
            cursor.execute("""
                INSERT INTO tablespace_usage_history (
                    sample_id, timestamp, tablespace, type, status, used_mb,
                    allocated_mb, max_mb, free_mb, pct_used, autoextend_headroom_mb,
                    files, autoextend_files, autoextend_capable
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sample_id, timestamp,
                ts.get('tablespace'),
                ts.get('type'),
                ts.get('status'),
                ts.get('used_mb'),
                ts.get('allocated_mb'),
                ts.get('max_mb'),
                ts.get('free_mb'),
                ts.get('pct_used'),
                ts.get('autoextend_headroom_mb'),
                ts.get('files'),
                ts.get('autoextend_files'),
                ts.get('autoextend_capable')
            ))
        
        conn.commit()
        conn.close()

