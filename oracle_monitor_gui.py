#!/usr/bin/env python3
"""
Oracle Database Session Monitor - GUI Version
Web-based monitoring dashboard using Streamlit
Read-only monitoring tool for Oracle 19+ databases
"""

import importlib
import json
import logging
import time
import sys
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from pathlib import Path

import oracledb
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

try:
    psutil = importlib.import_module("psutil")
except ImportError:  # pragma: no cover
    psutil = None

# Configure logging directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Configure file logging for AI analysis
log_formatter = logging.Formatter(
    '%(asctime)s|%(levelname)s|%(name)s|%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Main application log
app_logger = logging.getLogger('oracle_monitor_app')
app_logger.setLevel(logging.INFO)
app_handler = logging.FileHandler(LOG_DIR / 'app.log', encoding='utf-8')
app_handler.setFormatter(log_formatter)
app_logger.addHandler(app_handler)

# Metrics log (structured JSON)
metrics_logger = logging.getLogger('oracle_monitor_metrics')
metrics_logger.setLevel(logging.INFO)
metrics_handler = logging.FileHandler(LOG_DIR / 'metrics.jsonl', encoding='utf-8')
metrics_logger.addHandler(metrics_handler)

# Alerts log (structured JSON)
alerts_logger = logging.getLogger('oracle_monitor_alerts')
alerts_logger.setLevel(logging.WARNING)
alerts_handler = logging.FileHandler(LOG_DIR / 'alerts.jsonl', encoding='utf-8')
alerts_logger.addHandler(alerts_handler)

# Session details log (structured JSON)
sessions_logger = logging.getLogger('oracle_monitor_sessions')
sessions_logger.setLevel(logging.INFO)
sessions_handler = logging.FileHandler(LOG_DIR / 'sessions.jsonl', encoding='utf-8')
sessions_logger.addHandler(sessions_handler)

# Tablespace usage log (structured JSON)
tablespace_logger = logging.getLogger('oracle_monitor_tablespaces')
tablespace_logger.setLevel(logging.INFO)
tablespace_handler = logging.FileHandler(LOG_DIR / 'tablespaces.jsonl', encoding='utf-8')
tablespace_logger.addHandler(tablespace_handler)

# Storage I/O log (structured JSON)
io_logger = logging.getLogger('oracle_monitor_io')
io_logger.setLevel(logging.INFO)
io_handler = logging.FileHandler(LOG_DIR / 'io_sessions.jsonl', encoding='utf-8')
io_logger.addHandler(io_handler)

# Wait events log
waits_logger = logging.getLogger('oracle_monitor_waits')
waits_logger.setLevel(logging.INFO)
waits_handler = logging.FileHandler(LOG_DIR / 'wait_events.jsonl', encoding='utf-8')
waits_logger.addHandler(waits_handler)

# Temp usage log
temp_logger = logging.getLogger('oracle_monitor_temp')
temp_logger.setLevel(logging.INFO)
temp_handler = logging.FileHandler(LOG_DIR / 'temp_usage.jsonl', encoding='utf-8')
temp_logger.addHandler(temp_handler)

# Redo/log metrics log
redo_logger = logging.getLogger('oracle_monitor_redo')
redo_logger.setLevel(logging.INFO)
redo_handler = logging.FileHandler(LOG_DIR / 'redo_metrics.jsonl', encoding='utf-8')
redo_logger.addHandler(redo_handler)

# Plan churn log
plan_logger = logging.getLogger('oracle_monitor_plan')
plan_logger.setLevel(logging.INFO)
plan_handler = logging.FileHandler(LOG_DIR / 'plan_churn.jsonl', encoding='utf-8')
plan_logger.addHandler(plan_handler)

# Traffic logs
traffic_logger = logging.getLogger('oracle_monitor_traffic')
traffic_logger.setLevel(logging.INFO)
traffic_handler = logging.FileHandler(LOG_DIR / 'traffic_sessions.jsonl', encoding='utf-8')
traffic_logger.addHandler(traffic_handler)

traffic_groups_logger = logging.getLogger('oracle_monitor_traffic_groups')
traffic_groups_logger.setLevel(logging.INFO)
traffic_groups_handler = logging.FileHandler(LOG_DIR / 'traffic_groups.jsonl', encoding='utf-8')
traffic_groups_logger.addHandler(traffic_groups_handler)

# Configure page
st.set_page_config(
    page_title="Oracle Database Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False
if 'history' not in st.session_state:
    st.session_state.history = []
if 'connection' not in st.session_state:
    st.session_state.connection = None
if 'config' not in st.session_state:
    st.session_state.config = None


class HistoryStore:
    """Lightweight SQLite storage for monitoring history"""

    # --- START: __init__ ---
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    # --- END: __init__ ---

    # --- START: _connect ---
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn
    # --- END: _connect ---

    # --- START: _init_db ---
    def _init_db(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics_history (
                sample_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                total_sessions INTEGER,
                active_sessions INTEGER,
                inactive_sessions INTEGER,
                blocked_sessions INTEGER,
                logical_reads_mb REAL,
                physical_reads_mb REAL,
                cpu_seconds REAL,
                alert_count INTEGER,
                host_cpu_percent REAL,
                host_memory_percent REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tablespace_history (
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
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tablespace_history_ts ON tablespace_history(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tablespace_history_name ON tablespace_history(tablespace)"
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS io_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                sid INTEGER,
                serial INTEGER,
                username TEXT,
                program TEXT,
                status TEXT,
                sql_id TEXT,
                event TEXT,
                read_mb REAL,
                write_mb REAL,
                temp_mb REAL
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_io_history_ts ON io_history(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_io_history_sid ON io_history(sid)"
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wait_event_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                wait_class TEXT,
                event TEXT,
                sessions INTEGER,
                total_wait_seconds REAL,
                avg_wait_ms REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS temp_usage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                tablespace TEXT,
                username TEXT,
                program TEXT,
                segment_type TEXT,
                used_mb REAL,
                sid INTEGER,
                serial INTEGER,
                sql_id TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS undo_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                sample_time TEXT,
                undo_blocks INTEGER,
                transactions INTEGER,
                max_query_seconds REAL,
                ora1555 INTEGER,
                nospace_errors INTEGER,
                tuned_retention_seconds REAL,
                active_undo_bytes REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS redo_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                redo_size_bytes INTEGER,
                redo_writes INTEGER,
                redo_write_time_cs INTEGER,
                log_sync_waits INTEGER,
                log_sync_time_ms REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                sql_id TEXT,
                plan_hash TEXT,
                schema TEXT,
                module TEXT,
                executions INTEGER,
                elapsed_seconds REAL,
                buffer_gets INTEGER,
                disk_reads INTEGER,
                rows_processed INTEGER,
                last_active TEXT
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_wait_event_ts ON wait_event_history(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_temp_usage_ts ON temp_usage_history(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_history_sql ON plan_history(sql_id)"
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS all_sessions_traffic_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                sid INTEGER,
                serial INTEGER,
                username TEXT,
                program TEXT,
                machine TEXT,
                status TEXT,
                logon_time TEXT,
                last_call_et INTEGER,
                logical_reads_mb REAL,
                physical_reads_mb REAL,
                cpu_seconds REAL,
                wait_event TEXT,
                wait_time INTEGER,
                seconds_in_wait INTEGER,
                sql_id TEXT,
                blocking_session INTEGER,
                os_process TEXT
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_traffic_history_ts ON all_sessions_traffic_history(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_traffic_history_sid ON all_sessions_traffic_history(sid)"
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS grouped_traffic_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                username TEXT,
                program TEXT,
                status TEXT,
                session_count INTEGER,
                active_count INTEGER,
                inactive_count INTEGER,
                total_logical_reads_mb REAL,
                total_physical_reads_mb REAL,
                total_cpu_seconds REAL,
                machine_count INTEGER,
                blocked_count INTEGER
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_grouped_traffic_ts ON grouped_traffic_history(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_grouped_traffic_user ON grouped_traffic_history(username)"
        )
        conn.commit()
        conn.close()
    # --- END: _init_db ---

    # --- START: insert_metric ---
    def insert_metric(
        self,
        sample_id: str,
        timestamp_iso: str,
        overview: Dict,
        host_metrics: Optional[Dict] = None
    ):
        if not sample_id:
            sample_id = f"sample-{int(time.time() * 1000)}"
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO metrics_history (
                sample_id,
                timestamp,
                total_sessions,
                active_sessions,
                inactive_sessions,
                blocked_sessions,
                logical_reads_mb,
                physical_reads_mb,
                cpu_seconds,
                alert_count,
                host_cpu_percent,
                host_memory_percent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample_id,
                timestamp_iso,
                overview.get('total_sessions'),
                overview.get('active_sessions'),
                overview.get('inactive_sessions'),
                overview.get('blocked_sessions'),
                overview.get('logical_reads_mb'),
                overview.get('physical_reads_mb'),
                overview.get('cpu_seconds'),
                overview.get('alert_count'),
                (host_metrics or {}).get('cpu_percent'),
                (host_metrics or {}).get('memory_percent')
            )
        )
        conn.commit()
        conn.close()
    # --- END: insert_metric ---

    # --- START: insert_tablespaces ---
    def insert_tablespaces(
        self,
        sample_id: str,
        timestamp_iso: str,
        tablespaces: List[Dict]
    ):
        if not tablespaces:
            return
        conn = self._connect()
        cursor = conn.cursor()
        rows = [
            (
                sample_id,
                timestamp_iso,
                ts.get('Tablespace'),
                ts.get('Type'),
                ts.get('Status'),
                ts.get('Used MB'),
                ts.get('Allocated MB'),
                ts.get('Max MB'),
                ts.get('Free MB'),
                ts.get('Pct Used'),
                ts.get('Autoextend Headroom MB'),
                ts.get('Files'),
                ts.get('Autoextend Files'),
                1 if ts.get('Autoextend Capable') else 0
            )
            for ts in tablespaces
        ]
        cursor.executemany(
            """
            INSERT INTO tablespace_history (
                sample_id,
                timestamp,
                tablespace,
                type,
                status,
                used_mb,
                allocated_mb,
                max_mb,
                free_mb,
                pct_used,
                autoextend_headroom_mb,
                files,
                autoextend_files,
                autoextend_capable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        conn.commit()
        conn.close()
    # --- END: insert_tablespaces ---

    # --- START: insert_io_sessions ---
    def insert_io_sessions(
        self,
        sample_id: str,
        timestamp_iso: str,
        sessions: List[Dict]
    ):
        if not sessions:
            return
        conn = self._connect()
        cursor = conn.cursor()
        rows = [
            (
                sample_id,
                timestamp_iso,
                sess.get('SID'),
                sess.get('Serial#'),
                sess.get('Username'),
                sess.get('Program'),
                sess.get('Status'),
                sess.get('SQL ID'),
                sess.get('Event'),
                sess.get('Read MB'),
                sess.get('Write MB'),
                sess.get('Temp MB')
            )
            for sess in sessions
        ]
        cursor.executemany(
            """
            INSERT INTO io_history (
                sample_id,
                timestamp,
                sid,
                serial,
                username,
                program,
                status,
                sql_id,
                event,
                read_mb,
                write_mb,
                temp_mb
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        conn.commit()
        conn.close()
    # --- END: insert_io_sessions ---

    # --- START: insert_wait_events ---
    def insert_wait_events(self, sample_id: str, timestamp_iso: str, waits: List[Dict]):
        if not waits:
            return
        conn = self._connect()
        cursor = conn.cursor()
        rows = [
            (
                sample_id,
                timestamp_iso,
                wait.get('Wait Class'),
                wait.get('Event'),
                wait.get('Sessions'),
                wait.get('Total Wait (s)'),
                wait.get('Avg Wait (ms)')
            )
            for wait in waits
        ]
        cursor.executemany(
            """
            INSERT INTO wait_event_history (
                sample_id, timestamp, wait_class, event, sessions, total_wait_seconds, avg_wait_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        conn.commit()
        conn.close()
    # --- END: insert_wait_events ---

    # --- START: insert_temp_usage ---
    def insert_temp_usage(self, sample_id: str, timestamp_iso: str, temp_rows: List[Dict]):
        if not temp_rows:
            return
        conn = self._connect()
        cursor = conn.cursor()
        rows = [
            (
                sample_id,
                timestamp_iso,
                row.get('Tablespace'),
                row.get('Username'),
                row.get('Program'),
                row.get('Segment Type'),
                row.get('Used MB'),
                row.get('SID'),
                row.get('Serial#'),
                row.get('SQL ID')
            )
            for row in temp_rows
        ]
        cursor.executemany(
            """
            INSERT INTO temp_usage_history (
                sample_id, timestamp, tablespace, username, program, segment_type, used_mb, sid, serial, sql_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        conn.commit()
        conn.close()
    # --- END: insert_temp_usage ---

    # --- START: insert_undo_metrics ---
    def insert_undo_metrics(self, sample_id: str, timestamp_iso: str, undo_metrics: Dict):
        if not undo_metrics:
            return
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO undo_history (
                sample_id,
                timestamp,
                sample_time,
                undo_blocks,
                transactions,
                max_query_seconds,
                ora1555,
                nospace_errors,
                tuned_retention_seconds,
                active_undo_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample_id,
                timestamp_iso,
                undo_metrics.get('Sample Time'),
                undo_metrics.get('Undo Blocks'),
                undo_metrics.get('Transactions'),
                undo_metrics.get('Max Query (s)'),
                undo_metrics.get('ORA-01555 Errors'),
                undo_metrics.get('No Space Errors'),
                undo_metrics.get('Tuned Retention (s)'),
                undo_metrics.get('Active Undo (bytes)')
            )
        )
        conn.commit()
        conn.close()
    # --- END: insert_undo_metrics ---

    # --- START: insert_redo_metrics ---
    def insert_redo_metrics(self, sample_id: str, timestamp_iso: str, redo_metrics: Dict):
        if not redo_metrics:
            return
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO redo_history (
                sample_id,
                timestamp,
                redo_size_bytes,
                redo_writes,
                redo_write_time_cs,
                log_sync_waits,
                log_sync_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample_id,
                timestamp_iso,
                redo_metrics.get('Redo Size (bytes)'),
                redo_metrics.get('Redo Writes'),
                redo_metrics.get('Redo Write Time (cs)'),
                redo_metrics.get('Log File Sync Waits'),
                redo_metrics.get('Log File Sync Time (ms)')
            )
        )
        conn.commit()
        conn.close()
    # --- END: insert_redo_metrics ---

    # --- START: insert_plan_history ---
    def insert_plan_history(self, sample_id: str, timestamp_iso: str, plans: List[Dict]):
        if not plans:
            return
        conn = self._connect()
        cursor = conn.cursor()
        rows = [
            (
                sample_id,
                timestamp_iso,
                plan.get('SQL ID'),
                plan.get('Plan Hash'),
                plan.get('Schema'),
                plan.get('Module'),
                plan.get('Executions'),
                plan.get('Elapsed (s)'),
                plan.get('Buffer Gets'),
                plan.get('Disk Reads'),
                plan.get('Rows'),
                plan.get('Last Active')
            )
            for plan in plans
        ]
        cursor.executemany(
            """
            INSERT INTO plan_history (
                sample_id,
                timestamp,
                sql_id,
                plan_hash,
                schema,
                module,
                executions,
                elapsed_seconds,
                buffer_gets,
                disk_reads,
                rows_processed,
                last_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        conn.commit()
        conn.close()
    # --- END: insert_plan_history ---

    # --- START: fetch_recent_metrics ---
    def fetch_recent_metrics(self, limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sample_id, timestamp, total_sessions, active_sessions,
                   inactive_sessions, blocked_sessions, logical_reads_mb,
                   physical_reads_mb, cpu_seconds, alert_count,
                   host_cpu_percent, host_memory_percent
            FROM metrics_history
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'sample_id': row[0],
                'timestamp': row[1],
                'total_sessions': row[2],
                'active_sessions': row[3],
                'inactive_sessions': row[4],
                'blocked_sessions': row[5],
                'logical_reads_mb': row[6],
                'physical_reads_mb': row[7],
                'cpu_seconds': row[8],
                'alert_count': row[9],
                'host_cpu_percent': row[10],
                'host_memory_percent': row[11]
            }
            for row in rows
        ]
    # --- END: fetch_recent_metrics ---

    # --- START: list_tablespaces ---
    def list_tablespaces(self) -> List[str]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT tablespace FROM tablespace_history WHERE tablespace IS NOT NULL ORDER BY tablespace")
        rows = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        return rows
    # --- END: list_tablespaces ---

    # --- START: fetch_tablespace_history ---
    def fetch_tablespace_history(self, tablespace: Optional[str], limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        if tablespace:
            cursor.execute(
                """
                SELECT sample_id, timestamp, tablespace, type, status,
                       used_mb, allocated_mb, max_mb, free_mb, pct_used,
                       autoextend_headroom_mb, files, autoextend_files,
                       autoextend_capable
                FROM tablespace_history
                WHERE tablespace = ?
                ORDER BY datetime(timestamp) DESC
                LIMIT ?
                """,
                (tablespace, limit)
            )
        else:
            cursor.execute(
                """
                SELECT sample_id, timestamp, tablespace, type, status,
                       used_mb, allocated_mb, max_mb, free_mb, pct_used,
                       autoextend_headroom_mb, files, autoextend_files,
                       autoextend_capable
                FROM tablespace_history
                ORDER BY datetime(timestamp) DESC
                LIMIT ?
                """,
                (limit,)
            )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'sample_id': row[0],
                'timestamp': row[1],
                'tablespace': row[2],
                'type': row[3],
                'status': row[4],
                'used_mb': row[5],
                'allocated_mb': row[6],
                'max_mb': row[7],
                'free_mb': row[8],
                'pct_used': row[9],
                'autoextend_headroom_mb': row[10],
                'files': row[11],
                'autoextend_files': row[12],
                'autoextend_capable': bool(row[13])
            }
            for row in rows
        ]
    # --- END: fetch_tablespace_history ---

    # --- START: fetch_io_history ---
    def fetch_io_history(self, limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sample_id, timestamp, sid, serial, username, program, status,
                   sql_id, event, read_mb, write_mb, temp_mb
            FROM io_history
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'sample_id': row[0],
                'timestamp': row[1],
                'SID': row[2],
                'Serial#': row[3],
                'Username': row[4],
                'Program': row[5],
                'Status': row[6],
                'SQL ID': row[7],
                'Event': row[8],
                'Read MB': row[9],
                'Write MB': row[10],
                'Temp MB': row[11]
            }
            for row in rows
        ]
    # --- END: fetch_io_history ---

    # --- START: fetch_wait_history ---
    def fetch_wait_history(self, limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, wait_class, event, sessions, total_wait_seconds, avg_wait_ms
            FROM wait_event_history
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'timestamp': row[0],
                'Wait Class': row[1],
                'Event': row[2],
                'Sessions': row[3],
                'Total Wait (s)': row[4],
                'Avg Wait (ms)': row[5]
            }
            for row in rows
        ]
    # --- END: fetch_wait_history ---

    # --- START: fetch_temp_history ---
    def fetch_temp_history(self, limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, tablespace, username, program, segment_type, used_mb, sid, serial, sql_id
            FROM temp_usage_history
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'timestamp': row[0],
                'Tablespace': row[1],
                'Username': row[2],
                'Program': row[3],
                'Segment Type': row[4],
                'Used MB': row[5],
                'SID': row[6],
                'Serial#': row[7],
                'SQL ID': row[8]
            }
            for row in rows
        ]
    # --- END: fetch_temp_history ---

    # --- START: fetch_undo_history ---
    def fetch_undo_history(self, limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, sample_time, undo_blocks, transactions, max_query_seconds,
                   ora1555, nospace_errors, tuned_retention_seconds, active_undo_bytes
            FROM undo_history
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'timestamp': row[0],
                'Sample Time': row[1],
                'Undo Blocks': row[2],
                'Transactions': row[3],
                'Max Query (s)': row[4],
                'ORA-01555': row[5],
                'No Space Errors': row[6],
                'Tuned Retention (s)': row[7],
                'Active Undo (bytes)': row[8]
            }
            for row in rows
        ]
    # --- END: fetch_undo_history ---

    # --- START: fetch_redo_history ---
    def fetch_redo_history(self, limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, redo_size_bytes, redo_writes, redo_write_time_cs,
                   log_sync_waits, log_sync_time_ms
            FROM redo_history
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'timestamp': row[0],
                'Redo Size (bytes)': row[1],
                'Redo Writes': row[2],
                'Redo Write Time (cs)': row[3],
                'Log Sync Waits': row[4],
                'Log Sync Time (ms)': row[5]
            }
            for row in rows
        ]
    # --- END: fetch_redo_history ---

    # --- START: fetch_plan_history ---
    def fetch_plan_history(self, limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, sql_id, plan_hash, schema, module,
                   executions, elapsed_seconds, buffer_gets, disk_reads, rows_processed, last_active
            FROM plan_history
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'timestamp': row[0],
                'SQL ID': row[1],
                'Plan Hash': row[2],
                'Schema': row[3],
                'Module': row[4],
                'Executions': row[5],
                'Elapsed (s)': row[6],
                'Buffer Gets': row[7],
                'Disk Reads': row[8],
                'Rows': row[9],
                'Last Active': row[10]
            }
            for row in rows
        ]
    # --- END: fetch_plan_history ---

    # --- START: insert_all_sessions_traffic ---
    def insert_all_sessions_traffic(
        self,
        sample_id: str,
        timestamp_iso: str,
        sessions: List[Dict]
    ):
        if not sessions:
            return
        conn = self._connect()
        cursor = conn.cursor()
        for session in sessions:
            cursor.execute(
                """
                INSERT INTO all_sessions_traffic_history (
                    sample_id, timestamp, sid, serial, username, program, machine, status,
                    logon_time, last_call_et, logical_reads_mb, physical_reads_mb, cpu_seconds,
                    wait_event, wait_time, seconds_in_wait, sql_id, blocking_session, os_process
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    timestamp_iso,
                    session.get('SID'),
                    session.get('Serial#'),
                    session.get('Username'),
                    session.get('Program'),
                    session.get('Machine'),
                    session.get('Status'),
                    session.get('Logon Time'),
                    session.get('Last Call (sec)'),
                    session.get('Logical Reads (MB)'),
                    session.get('Physical Reads (MB)'),
                    session.get('CPU (seconds)'),
                    session.get('Wait Event'),
                    session.get('Wait Time'),
                    session.get('Seconds in Wait'),
                    session.get('SQL ID'),
                    session.get('Blocking Session'),
                    session.get('OS Process')
                )
            )
        conn.commit()
        conn.close()
    # --- END: insert_all_sessions_traffic ---

    # --- START: insert_grouped_traffic ---
    def insert_grouped_traffic(
        self,
        sample_id: str,
        timestamp_iso: str,
        grouped_sessions: List[Dict]
    ):
        if not grouped_sessions:
            return
        conn = self._connect()
        cursor = conn.cursor()
        for group in grouped_sessions:
            cursor.execute(
                """
                INSERT INTO grouped_traffic_history (
                    sample_id, timestamp, username, program, status, session_count,
                    active_count, inactive_count, total_logical_reads_mb, total_physical_reads_mb,
                    total_cpu_seconds, machine_count, blocked_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    timestamp_iso,
                    group.get('Username'),
                    group.get('Program'),
                    group.get('Status'),
                    group.get('Total Sessions'),
                    group.get('Active Sessions'),
                    group.get('Inactive Sessions'),
                    group.get('Total Logical Reads (MB)'),
                    group.get('Total Physical Reads (MB)'),
                    group.get('Total CPU (seconds)'),
                    group.get('Machines'),
                    group.get('Blocked Sessions')
                )
            )
        conn.commit()
        conn.close()
    # --- END: insert_grouped_traffic ---

    # --- START: fetch_all_sessions_traffic_history ---
    def fetch_all_sessions_traffic_history(self, limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, sid, serial, username, program, machine, status,
                   logon_time, last_call_et, logical_reads_mb, physical_reads_mb, cpu_seconds,
                   wait_event, wait_time, seconds_in_wait, sql_id, blocking_session, os_process
            FROM all_sessions_traffic_history
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'timestamp': row[0],
                'SID': row[1],
                'Serial#': row[2],
                'Username': row[3],
                'Program': row[4],
                'Machine': row[5],
                'Status': row[6],
                'Logon Time': row[7],
                'Last Call (sec)': row[8],
                'Logical Reads (MB)': row[9],
                'Physical Reads (MB)': row[10],
                'CPU (seconds)': row[11],
                'Wait Event': row[12],
                'Wait Time': row[13],
                'Seconds in Wait': row[14],
                'SQL ID': row[15],
                'Blocking Session': row[16],
                'OS Process': row[17]
            }
            for row in rows
        ]
    # --- END: fetch_all_sessions_traffic_history ---

    # --- START: fetch_grouped_traffic_history ---
    def fetch_grouped_traffic_history(self, limit: int = 200) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, username, program, status, session_count,
                   active_count, inactive_count, total_logical_reads_mb, total_physical_reads_mb,
                   total_cpu_seconds, machine_count, blocked_count
            FROM grouped_traffic_history
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'timestamp': row[0],
                'Username': row[1],
                'Program': row[2],
                'Status': row[3],
                'Total Sessions': row[4],
                'Active Sessions': row[5],
                'Inactive Sessions': row[6],
                'Total Logical Reads (MB)': row[7],
                'Total Physical Reads (MB)': row[8],
                'Total CPU (seconds)': row[9],
                'Machines': row[10],
                'Blocked Sessions': row[11]
            }
            for row in rows
        ]
    # --- END: fetch_grouped_traffic_history ---


class OracleMonitorGUI:
    """Oracle Database Session Monitor GUI - Read-only monitoring"""
    
    # --- START: __init__ ---
    def __init__(self):
        """Initialize monitor"""
        self.connection: Optional[oracledb.Connection] = None
        self.log_dir = LOG_DIR
        self.metrics_csv_path = self.log_dir / 'metrics.csv'
        self.tablespace_csv_path = self.log_dir / 'tablespace_usage.csv'
        self.io_csv_path = self.log_dir / 'io_sessions.csv'
        self.history_db_path = self.log_dir / 'monitor_history.db'
        self.history_store = HistoryStore(self.history_db_path)
        self._init_csv_logs()
        self._process_handle = None
    # --- END: __init__ ---
    
    # --- START: _init_csv_logs ---
    def _init_csv_logs(self):
        """Initialize CSV log files with headers"""
        # Metrics CSV
        if not self.metrics_csv_path.exists():
            with open(self.metrics_csv_path, 'w', encoding='utf-8', newline='') as f:
                f.write('timestamp,total_sessions,active_sessions,inactive_sessions,blocked_sessions,'
                        'logical_reads_mb,physical_reads_mb,cpu_seconds,alert_count\n')
        if not self.tablespace_csv_path.exists():
            with open(self.tablespace_csv_path, 'w', encoding='utf-8', newline='') as f:
                f.write('timestamp,tablespace_name,type,status,used_mb,allocated_mb,max_mb,free_mb,'
                        'pct_used,autoextend_headroom_mb,file_count,auto_file_count\n')
        if not self.io_csv_path.exists():
            with open(self.io_csv_path, 'w', encoding='utf-8', newline='') as f:
                f.write('timestamp,sid,serial,username,program,status,sql_id,event,read_mb,write_mb,temp_mb\n')
    # --- END: _init_csv_logs ---
    
    # --- START: _log_metrics_json ---
    def _log_metrics_json(
        self,
        metrics: Dict,
        sample_meta: Optional[Dict] = None,
        host_metrics: Optional[Dict] = None,
        resource_limits: Optional[Dict] = None
    ):
        """Log metrics in JSON Lines format for AI analysis"""
        timestamp = metrics.get('timestamp', datetime.now())
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
        else:
            timestamp = str(timestamp)

        log_entry = {
            'timestamp': timestamp,
            'sample_id': sample_meta.get('sample_id') if sample_meta else None,
            'interval_seconds': sample_meta.get('interval_seconds') if sample_meta else None,
            'type': 'metrics',
            'data': {
                'total_sessions': metrics.get('total_sessions', 0),
                'active_sessions': metrics.get('active_sessions', 0),
                'inactive_sessions': metrics.get('inactive_sessions', 0),
                'blocked_sessions': metrics.get('blocked_sessions', 0),
                'logical_reads_mb': metrics.get('logical_reads_mb', 0),
                'physical_reads_mb': metrics.get('physical_reads_mb', 0),
                'cpu_seconds': metrics.get('cpu_seconds', 0),
                'alert_count': metrics.get('alert_count', 0)
            },
            'overview': sample_meta.get('overview') if sample_meta else {},
            'thresholds': sample_meta.get('thresholds') if sample_meta else {}
        }

        if host_metrics:
            log_entry['host_metrics'] = host_metrics

        if resource_limits:
            log_entry['resource_limits'] = resource_limits

        metrics_logger.info(json.dumps(log_entry, ensure_ascii=False))

        if self.history_store and sample_meta:
            sample_id = sample_meta.get('sample_id')
            timestamp_value = metrics.get('timestamp', datetime.now(timezone.utc))
            if isinstance(timestamp_value, datetime):
                timestamp_iso = timestamp_value.astimezone(timezone.utc).isoformat()
            else:
                timestamp_iso = str(timestamp_value)
            try:
                self.history_store.insert_metric(
                    sample_id=sample_id,
                    timestamp_iso=timestamp_iso,
                    overview=metrics,
                    host_metrics=host_metrics
                )
            except Exception as exc:
                app_logger.error(f"Failed to persist metrics to SQLite: {exc}")
    # --- END: _log_metrics_json ---
    
    # --- START: _log_metrics_csv ---
    def _log_metrics_csv(
        self,
        metrics: Dict,
        sample_meta: Optional[Dict] = None,
        host_metrics: Optional[Dict] = None
    ):
        """Log metrics to CSV file"""
        try:
            with open(self.metrics_csv_path, 'a', encoding='utf-8', newline='') as f:
                timestamp = metrics.get('timestamp', datetime.now())
                if isinstance(timestamp, datetime):
                    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    timestamp_str = str(timestamp)
                
                f.write(f"{timestamp_str},"
                       f"{metrics.get('total_sessions', 0)},"
                       f"{metrics.get('active_sessions', 0)},"
                       f"{metrics.get('inactive_sessions', 0)},"
                       f"{metrics.get('blocked_sessions', 0)},"
                       f"{metrics.get('logical_reads_mb', 0):.2f},"
                       f"{metrics.get('physical_reads_mb', 0):.2f},"
                       f"{metrics.get('cpu_seconds', 0):.2f},"
                       f"{metrics.get('alert_count', 0)}\n")
        except Exception as e:
            app_logger.error(f"Failed to write CSV metrics: {e}")
    # --- END: _log_metrics_csv ---
    
    # --- START: _log_alert ---
    def _log_alert(self, alert_type: str, message: str, details: Dict = None):
        """Log alerts in JSON Lines format"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'alert',
            'alert_type': alert_type,  # 'warning', 'critical', 'info'
            'message': message,
            'details': details or {}
        }
        alerts_logger.warning(json.dumps(log_entry, ensure_ascii=False))
        app_logger.warning(f"ALERT [{alert_type}]: {message}")
    # --- END: _log_alert ---
    
    # --- START: _log_sessions ---
    def _log_sessions(
        self,
        sessions: List[Dict],
        session_type: str = 'top',
        sample_meta: Optional[Dict] = None,
        extra: Optional[Dict] = None
    ):
        """Log session details in JSON Lines format"""
        if not sessions:
            return

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'session_batch',
            'session_type': session_type,  # 'top', 'blocking', 'blocked', 'cpu', 'resource'
            'sessions': sessions
        }

        if sample_meta:
            log_entry['sample'] = sample_meta

        if extra:
            log_entry['extra'] = extra

        sessions_logger.info(json.dumps(log_entry, ensure_ascii=False))
    # --- END: _log_sessions ---

    # --- START: _log_tablespaces ---
    def _log_tablespaces(
        self,
        tablespaces: List[Dict],
        sample_meta: Optional[Dict] = None
    ):
        """Log tablespace usage in JSON Lines format"""
        if not tablespaces:
            return

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'tablespace_batch',
            'tablespaces': tablespaces
        }
        if sample_meta:
            log_entry['sample'] = sample_meta

        tablespace_logger.info(json.dumps(log_entry, ensure_ascii=False))

        # Append to CSV for offline analysis
        try:
            with open(self.tablespace_csv_path, 'a', encoding='utf-8', newline='') as f:
                for ts in tablespaces:
                    f.write(
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')},"
                        f"{ts.get('Tablespace','')},"
                        f"{ts.get('Type','')},"
                        f"{ts.get('Status','')},"
                        f"{ts.get('Used MB',0):.2f},"
                        f"{ts.get('Allocated MB',0):.2f},"
                        f"{ts.get('Max MB',0):.2f},"
                        f"{ts.get('Free MB',0):.2f},"
                        f"{ts.get('Pct Used',0):.2f},"
                        f"{ts.get('Autoextend Headroom MB',0):.2f},"
                        f"{ts.get('Files',0)},"
                        f"{ts.get('Autoextend Files',0)}\n"
                    )
        except Exception as e:
            app_logger.error(f"Failed to write tablespace CSV: {e}")
        if self.history_store and sample_meta:
            timestamp_iso = sample_meta.get('generated_at')
            if not timestamp_iso:
                timestamp_iso = datetime.now(timezone.utc).isoformat()
            try:
                self.history_store.insert_tablespaces(
                    sample_meta.get('sample_id'),
                    timestamp_iso,
                    tablespaces
                )
            except Exception as exc:
                app_logger.error(f"Failed to persist tablespaces to SQLite: {exc}")
    # --- END: _log_tablespaces ---

    # --- START: _log_io_sessions ---
    def _log_io_sessions(
        self,
        io_sessions: List[Dict],
        sample_meta: Optional[Dict] = None
    ):
        """Log storage I/O heavy sessions"""
        if not io_sessions:
            return

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'io_sessions',
            'sessions': io_sessions
        }
        if sample_meta:
            log_entry['sample'] = sample_meta
        io_logger.info(json.dumps(log_entry, ensure_ascii=False))

        try:
            with open(self.io_csv_path, 'a', encoding='utf-8', newline='') as f:
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for sess in io_sessions:
                    f.write(
                        f"{ts},"
                        f"{sess.get('SID','')},"
                        f"{sess.get('Serial#','')},"
                        f"{sess.get('Username','')},"
                        f"{sess.get('Program','')},"
                        f"{sess.get('Status','')},"
                        f"{sess.get('SQL ID','')},"
                        f"{sess.get('Event','')},"
                        f"{sess.get('Read MB',0):.2f},"
                        f"{sess.get('Write MB',0):.2f},"
                        f"{sess.get('Temp MB',0):.2f}\n"
                    )
        except Exception as e:
            app_logger.error(f"Failed to write IO CSV: {e}")

        if self.history_store and sample_meta:
            timestamp_iso = sample_meta.get('generated_at') or datetime.now(timezone.utc).isoformat()
            try:
                self.history_store.insert_io_sessions(
                    sample_meta.get('sample_id'),
                    timestamp_iso,
                    io_sessions
                )
            except Exception as exc:
                app_logger.error(f"Failed to persist IO sessions to SQLite: {exc}")
    # --- END: _log_io_sessions ---

    # --- START: _log_wait_events ---
    def _log_wait_events(self, waits: List[Dict], sample_meta: Optional[Dict] = None):
        if not waits:
            return
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'wait_events',
            'waits': waits,
            'sample': sample_meta or {}
        }
        waits_logger.info(json.dumps(log_entry, ensure_ascii=False))
    # --- END: _log_wait_events ---

    # --- START: _log_temp_usage ---
    def _log_temp_usage(self, temp_rows: List[Dict], undo_metrics: Dict, sample_meta: Optional[Dict] = None):
        if temp_rows:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'type': 'temp_usage',
                'rows': temp_rows,
                'sample': sample_meta or {}
            }
            temp_logger.info(json.dumps(log_entry, ensure_ascii=False))
        if undo_metrics:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'type': 'undo_metrics',
                'metrics': undo_metrics,
                'sample': sample_meta or {}
            }
            temp_logger.info(json.dumps(log_entry, ensure_ascii=False))
    # --- END: _log_temp_usage ---

    # --- START: _log_redo_metrics ---
    def _log_redo_metrics(self, redo_metrics: Dict, sample_meta: Optional[Dict] = None):
        if not redo_metrics:
            return
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'redo_metrics',
            'metrics': redo_metrics,
            'sample': sample_meta or {}
        }
        redo_logger.info(json.dumps(log_entry, ensure_ascii=False))
    # --- END: _log_redo_metrics ---

    # --- START: _log_plan_churn ---
    def _log_plan_churn(self, plan_rows: List[Dict], sample_meta: Optional[Dict] = None):
        if not plan_rows:
            return
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'plan_churn',
            'plans': plan_rows,
            'sample': sample_meta or {}
        }
        plan_logger.info(json.dumps(log_entry, ensure_ascii=False))
    # --- END: _log_plan_churn ---

    # --- START: _log_traffic_sessions ---
    def _log_traffic_sessions(
        self,
        sessions: List[Dict],
        sample_meta: Optional[Dict] = None
    ):
        """Log all session traffic snapshots to JSON Lines"""
        if not sessions:
            return

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'traffic_all',
            'session_count': len(sessions),
            'sessions': sessions
        }

        if sample_meta:
            log_entry['sample'] = sample_meta

        traffic_logger.info(json.dumps(log_entry, ensure_ascii=False))
    # --- END: _log_traffic_sessions ---

    # --- START: _log_grouped_traffic ---
    def _log_grouped_traffic(
        self,
        grouped_rows: List[Dict],
        sample_meta: Optional[Dict] = None
    ):
        """Log grouped traffic aggregates (user/program)"""
        if not grouped_rows:
            return

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'traffic_grouped',
            'group_count': len(grouped_rows),
            'groups': grouped_rows
        }

        if sample_meta:
            log_entry['sample'] = sample_meta

        traffic_groups_logger.info(json.dumps(log_entry, ensure_ascii=False))
    # --- END: _log_grouped_traffic ---

    # --- START: group_sessions ---
    def group_sessions(self, sessions: List[Dict], group_mode: str = 'user_program') -> List[Dict]:
        """Group sessions to identify swarms of short jobs"""
        if not sessions:
            return []

        grouped = {}
        for sess in sessions:
            username = sess.get('Username') or sess.get('username') or 'N/A'
            program = sess.get('Program') or sess.get('program') or 'N/A'
            sql_id = sess.get('SQL ID') or sess.get('sql_id') or 'N/A'
            module = sess.get('Module') or sess.get('module') or 'N/A'

            if group_mode == 'user':
                key = username
            elif group_mode == 'program':
                key = program
            elif group_mode == 'sql':
                key = sql_id
            elif group_mode == 'module':
                key = module
            else:  # user_program default
                key = f"{username} | {program}"

            entry = grouped.setdefault(key, {
                'Group Key': key,
                'Username': username,
                'Program': program,
                'Module': module,
                'SQL ID': sql_id,
                'Session Count': 0,
                'Total CPU (s)': 0.0,
                'Total PGA (MB)': 0.0,
                'Sample SQL Text': '',
                'Sample SQL ID': sql_id
            })

            entry['Session Count'] += 1
            entry['Total CPU (s)'] += float(sess.get('CPU (seconds)', 0) or 0)
            entry['Total PGA (MB)'] += float(sess.get('PGA (MB)', 0) or 0)
            if not entry['Sample SQL Text'] and (sess.get('SQL Text Full') or sess.get('SQL Text')):
                entry['Sample SQL Text'] = sess.get('SQL Text Full') or sess.get('SQL Text')
                entry['Sample SQL ID'] = sql_id

        return sorted(grouped.values(), key=lambda x: (x['Session Count'], x['Total CPU (s)']), reverse=True)
    # --- END: group_sessions ---
    
    # --- START: get_host_metrics ---
    def get_host_metrics(self) -> Dict:
        """Collect host-level CPU/memory statistics using psutil"""
        if psutil is None:
            return {}

        try:
            cpu_percent = psutil.cpu_percent(interval=0.2)
            cpu_count = psutil.cpu_count(logical=True) or 0
            virt = psutil.virtual_memory()
            swap = psutil.swap_memory()
            if self._process_handle is None:
                self._process_handle = psutil.Process(os.getpid())
                # Prime CPU percent to establish baseline
                self._process_handle.cpu_percent(interval=None)
            process = self._process_handle
            process_cpu = process.cpu_percent(interval=None)
            if process_cpu == 0.0:
                process_cpu = process.cpu_percent(interval=0.1)
            process_mem = process.memory_info().rss / (1024 * 1024)  # MB
            load_avg = (0.0, 0.0, 0.0)
            if hasattr(os, 'getloadavg'):
                try:
                    load_avg = os.getloadavg()
                except OSError:
                    load_avg = (0.0, 0.0, 0.0)

            return {
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'process_cpu_percent': process_cpu,
                'memory_percent': virt.percent,
                'memory_used_gb': virt.used / (1024 ** 3),
                'memory_total_gb': virt.total / (1024 ** 3),
                'swap_percent': swap.percent,
                'load_avg': load_avg,
                'process_memory_mb': process_mem
            }
        except Exception as e:
            app_logger.error(f"Failed to collect host metrics: {e}")
            return {}
    # --- END: get_host_metrics ---
    
    # --- START: get_session_resource_usage ---
    def get_session_resource_usage(self, limit: int = 15) -> List[Dict]:
        """Get detailed CPU/memory/thread usage per session - READ ONLY"""
        if not self.connection:
            return []

        try:
            cursor = self.connection.cursor()
            try:
                stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')
                stat_pga = self._get_statistic_id(cursor, 'session pga memory')
                stat_pga_max = self._get_statistic_id(cursor, 'session pga memory max')

                if not stat_cpu and not stat_pga:
                    return []

                query = """
                    SELECT
                        s.sid,
                        s.serial#,
                        s.username,
                        s.status,
                        s.program,
                        s.machine,
                        p.spid AS os_thread,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_cpu THEN stat.value ELSE 0 END) / 100, 2) AS cpu_seconds,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_pga THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS pga_mb,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_pga_max THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS pga_max_mb,
                        s.sql_id,
                        q.sql_text,
                        q.plan_hash_value,
                        q.module,
                        q.action
                    FROM v$session s
                    LEFT JOIN v$process p ON s.paddr = p.addr
                    LEFT JOIN v$sesstat stat ON s.sid = stat.sid
                        AND stat.statistic# IN (:stat_cpu, :stat_pga, :stat_pga_max)
                    LEFT JOIN v$sql q ON s.sql_id = q.sql_id
                    WHERE s.username IS NOT NULL
                    GROUP BY s.sid, s.serial#, s.username, s.status, s.program, s.machine, p.spid, s.sql_id,
                             q.sql_text, q.plan_hash_value, q.module, q.action
                    ORDER BY MAX(CASE WHEN stat.statistic# = :stat_cpu THEN stat.value ELSE 0 END) DESC
                    FETCH FIRST :limit ROWS ONLY
                """

                cursor.execute(query, {
                    'stat_cpu': stat_cpu or -1,
                    'stat_pga': stat_pga or -1,
                    'stat_pga_max': stat_pga_max or -1,
                    'limit': limit
                })

                sessions = []
                for row in cursor:
                    full_sql = (row[11] or '').strip()
                    sessions.append({
                        'SID': row[0],
                        'Serial#': row[1],
                        'Username': row[2] or 'N/A',
                        'Status': row[3] or 'N/A',
                        'Program': row[4] or 'N/A',
                        'Machine': row[5] or 'N/A',
                        'OS Thread': row[6] or 'N/A',
                        'CPU (seconds)': float(row[7] or 0),
                        'PGA (MB)': float(row[8] or 0),
                        'PGA Max (MB)': float(row[9] or 0),
                        'SQL ID': row[10] or 'N/A',
                        'SQL Text': full_sql[:500],
                        'SQL Text Full': full_sql,
                        'Plan Hash': str(row[12]) if row[12] is not None else 'N/A',
                        'Module': row[13] or 'N/A',
                        'Action': row[14] or 'N/A'
                    })
            finally:
                cursor.close()

            total_cpu = sum(item['CPU (seconds)'] for item in sessions) or 0
            total_pga = sum(item['PGA (MB)'] for item in sessions) or 0
            for item in sessions:
                item['CPU %'] = round((item['CPU (seconds)'] / total_cpu) * 100, 2) if total_cpu > 0 else 0.0
                item['Memory %'] = round((item['PGA (MB)'] / total_pga) * 100, 2) if total_pga > 0 else 0.0

            return sessions

        except oracledb.Error as e:
            st.error(f"Error getting resource usage: {e}")
            return []
    # --- END: get_session_resource_usage ---

    # --- START: get_io_sessions ---
    def get_io_sessions(self, limit: int = 15) -> List[Dict]:
        """Get sessions with highest physical I/O usage - READ ONLY"""
        if not self.connection:
            return []

        try:
            cursor = self.connection.cursor()
            try:
                stat_read_bytes = self._get_statistic_id(cursor, 'physical read bytes')
                stat_write_bytes = self._get_statistic_id(cursor, 'physical write bytes')
                stat_temp_bytes = self._get_statistic_id(cursor, 'temp space allocated')

                if not stat_read_bytes and not stat_write_bytes:
                    return []

                query = """
                    SELECT
                        s.sid,
                        s.serial#,
                        s.username,
                        s.program,
                        s.status,
                        s.sql_id,
                        s.event,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_read_bytes THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS read_mb,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_write_bytes THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS write_mb,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_temp_bytes THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS temp_mb,
                        q.sql_text,
                        q.plan_hash_value,
                        q.module,
                        q.action
                    FROM v$session s
                    LEFT JOIN v$sesstat stat ON s.sid = stat.sid
                        AND stat.statistic# IN (:stat_read_bytes, :stat_write_bytes, :stat_temp_bytes)
                    LEFT JOIN v$sql q ON s.sql_id = q.sql_id
                    WHERE s.username IS NOT NULL
                    GROUP BY s.sid, s.serial#, s.username, s.program, s.status, s.sql_id, s.event,
                             q.sql_text, q.plan_hash_value, q.module, q.action
                    ORDER BY (MAX(CASE WHEN stat.statistic# = :stat_read_bytes THEN stat.value ELSE 0 END) +
                              MAX(CASE WHEN stat.statistic# = :stat_write_bytes THEN stat.value ELSE 0 END)) DESC
                    FETCH FIRST :limit ROWS ONLY
                """

                cursor.execute(query, {
                    'stat_read_bytes': stat_read_bytes or -1,
                    'stat_write_bytes': stat_write_bytes or -1,
                    'stat_temp_bytes': stat_temp_bytes or -1,
                    'limit': limit
                })

                sessions = []
                for row in cursor:
                    full_sql = (row[10] or '').strip()
                    sessions.append({
                        'SID': row[0],
                        'Serial#': row[1],
                        'Username': row[2] or 'N/A',
                        'Program': row[3] or 'N/A',
                        'Status': row[4] or 'N/A',
                        'SQL ID': row[5] or 'N/A',
                        'Event': row[6] or 'N/A',
                        'Read MB': float(row[7] or 0),
                        'Write MB': float(row[8] or 0),
                        'Temp MB': float(row[9] or 0),
                        'SQL Text': full_sql[:500],
                        'SQL Text Full': full_sql,
                        'Plan Hash': str(row[11]) if row[11] is not None else 'N/A',
                        'Module': row[12] or 'N/A',
                        'Action': row[13] or 'N/A'
                    })
            finally:
                cursor.close()

            total_read = sum(sess['Read MB'] for sess in sessions) or 0
            total_write = sum(sess['Write MB'] for sess in sessions) or 0
            for sess in sessions:
                sess['Read %'] = round((sess['Read MB'] / total_read) * 100, 2) if total_read > 0 else 0.0
                sess['Write %'] = round((sess['Write MB'] / total_write) * 100, 2) if total_write > 0 else 0.0

            return sessions

        except oracledb.Error as e:
            st.error(f"Error getting IO sessions: {e}")
            return []
    # --- END: get_io_sessions ---

    # --- START: get_wait_events ---
    def get_wait_events(self, limit: int = 10) -> List[Dict]:
        if not self.connection:
            return []
        try:
            cursor = self.connection.cursor()
            try:
                query = """
                    SELECT
                        NVL(en.wait_class, 'Other') AS wait_class,
                        se.event,
                        se.total_waits AS sessions_waiting,
                        ROUND(se.time_waited / 100, 2) AS total_wait_seconds,
                        ROUND(CASE WHEN se.total_waits = 0 THEN 0
                               ELSE (se.time_waited / se.total_waits) * 10 END, 2) AS avg_wait_ms
                    FROM v$session_event se
                    JOIN v$event_name en ON se.event = en.name
                    WHERE en.wait_class NOT IN ('Idle')
                    ORDER BY se.time_waited DESC
                    FETCH FIRST :limit ROWS ONLY
                """
                cursor.execute(query, {'limit': limit})
                waits = []
                for row in cursor:
                    waits.append({
                        'Wait Class': row[0],
                        'Event': row[1],
                        'Sessions': row[2],
                        'Total Wait (s)': float(row[3] or 0),
                        'Avg Wait (ms)': float(row[4] or 0)
                    })
            finally:
                cursor.close()
            return waits
        except oracledb.Error as e:
            st.error(f"Error getting wait events: {e}")
            return []
    # --- END: get_wait_events ---

    # --- START: get_temp_usage ---
    def get_temp_usage(self, limit: int = 15) -> List[Dict]:
        if not self.connection:
            return []
        try:
            cursor = self.connection.cursor()
            try:
                query = """
                    SELECT
                        tu.tablespace,
                        NVL(s.username, 'N/A') AS username,
                        NVL(s.program, 'N/A') AS program,
                        tu.segtype,
                        ROUND(SUM(tu.blocks * dt.block_size) / 1024 / 1024, 2) AS used_mb,
                        MIN(s.sid) AS sid,
                        MIN(s.serial#) AS serial#,
                        MAX(tu.sql_id) AS sql_id
                    FROM v$tempseg_usage tu
                    JOIN dba_tablespaces dt ON dt.tablespace_name = tu.tablespace
                    LEFT JOIN v$session s ON tu.session_addr = s.saddr
                    GROUP BY tu.tablespace, s.username, s.program, tu.segtype
                    ORDER BY used_mb DESC
                    FETCH FIRST :limit ROWS ONLY
                """
                cursor.execute(query, {'limit': limit})
                rows = []
                for row in cursor:
                    rows.append({
                        'Tablespace': row[0],
                        'Username': row[1],
                        'Program': row[2],
                        'Segment Type': row[3],
                        'Used MB': float(row[4] or 0),
                        'SID': row[5],
                        'Serial#': row[6],
                        'SQL ID': row[7] or 'N/A'
                    })
            finally:
                cursor.close()
            return rows
        except oracledb.Error as e:
            st.error(f"Error getting temp usage: {e}")
            return []
    # --- END: get_temp_usage ---

    # --- START: get_undo_metrics ---
    def get_undo_metrics(self) -> Dict:
        if not self.connection:
            return {}
        try:
            cursor = self.connection.cursor()
            try:
                query = """
                    SELECT
                        TO_CHAR(end_time, 'YYYY-MM-DD HH24:MI:SS') AS end_time,
                        undoblks,
                        txncount,
                        maxquerylen,
                        ssolderrcnt,
                        nospaceerrcnt,
                        tuned_undoretention
                    FROM v$undostat
                    ORDER BY end_time DESC
                    FETCH FIRST 1 ROW ONLY
                """
                cursor.execute(query)
                row = cursor.fetchone()
            finally:
                cursor.close()
            if row:
                return {
                    'Sample Time': row[0],
                    'Undo Blocks': row[1],
                    'Transactions': row[2],
                    'Max Query (s)': row[3],
                    'ORA-01555 Errors': row[4],
                    'No Space Errors': row[5],
                    'Tuned Retention (s)': row[6]
                }
            return {}
        except oracledb.Error as e:
            st.error(f"Error getting undo metrics: {e}")
            return {}
    # --- END: get_undo_metrics ---

    # --- START: get_redo_metrics ---
    def get_redo_metrics(self) -> Dict:
        if not self.connection:
            return {}
        try:
            cursor = self.connection.cursor()
            try:
                sysstat_query = """
                    SELECT name, value
                    FROM v$sysstat
                    WHERE name IN ('redo size', 'redo writes', 'redo write time')
                """
                cursor.execute(sysstat_query)
                stats = {row[0]: row[1] for row in cursor}

                event_query = """
                    SELECT total_waits, time_waited_micro
                    FROM v$system_event
                    WHERE event = 'log file sync'
                """
                cursor.execute(event_query)
                event_row = cursor.fetchone()
                log_sync_waits = event_row[0] if event_row else None
                log_sync_time = event_row[1] / 1000 if event_row else None
            finally:
                cursor.close()

            return {
                'Redo Size (bytes)': stats.get('redo size'),
                'Redo Writes': stats.get('redo writes'),
                'Redo Write Time (cs)': stats.get('redo write time'),
                'Log File Sync Waits': log_sync_waits,
                'Log File Sync Time (ms)': log_sync_time
            }
        except oracledb.Error as e:
            st.error(f"Error getting redo metrics: {e}")
            return {}
    # --- END: get_redo_metrics ---

    # --- START: get_blocking_chains ---
    def get_blocking_chains(self) -> List[Dict]:
        if not self.connection:
            return []
        try:
            cursor = self.connection.cursor()
            try:
                query = """
                    SELECT *
                    FROM (
                        SELECT
                            CONNECT_BY_ROOT s.sid AS root_sid,
                            CONNECT_BY_ROOT s.serial# AS root_serial,
                            LEVEL AS depth,
                            s.sid,
                            s.serial#,
                            s.username,
                            s.program,
                            s.event,
                            s.seconds_in_wait,
                            s.blocking_session
                        FROM v$session s
                        WHERE s.username IS NOT NULL
                        CONNECT BY PRIOR s.sid = s.blocking_session
                    )
                    WHERE depth > 1
                    ORDER BY root_sid, depth
                """
                cursor.execute(query)
                chains = []
                for row in cursor:
                    chains.append({
                        'Root SID': row[0],
                        'Root Serial#': row[1],
                        'Depth': row[2],
                        'SID': row[3],
                        'Serial#': row[4],
                        'Username': row[5] or 'N/A',
                        'Program': row[6] or 'N/A',
                        'Event': row[7] or 'N/A',
                        'Seconds in Wait': row[8] or 0,
                        'Blocking SID': row[9]
                    })
            finally:
                cursor.close()
            return chains
        except oracledb.Error as e:
            st.error(f"Error getting blocking chains: {e}")
            return []
    # --- END: get_blocking_chains ---

    # --- START: get_plan_churn ---
    def get_plan_churn(self, limit: int = 10) -> List[Dict]:
        if not self.connection:
            return []
        try:
            cursor = self.connection.cursor()
            try:
                query = """
                    SELECT
                        q.sql_id,
                        q.plan_hash_value,
                        NVL(s.parsing_schema_name, 'N/A') AS schema,
                        NVL(s.module, 'N/A') AS module,
                        q.executions,
                        ROUND(q.elapsed_time / 1000000, 2) AS elapsed_seconds,
                        q.buffer_gets,
                        q.disk_reads,
                        q.rows_processed,
                        TO_CHAR(q.last_active_time, 'YYYY-MM-DD HH24:MI:SS') AS last_active,
                        s.sql_text
                    FROM v$sqlstats q
                    LEFT JOIN v$sql s ON q.sql_id = s.sql_id AND q.plan_hash_value = s.plan_hash_value
                    WHERE q.last_active_time > SYSDATE - (1/24)
                    ORDER BY q.executions DESC
                    FETCH FIRST :limit ROWS ONLY
                """
                cursor.execute(query, {'limit': limit})
                plans = []
                for row in cursor:
                    text = (row[10] or '').strip()
                    plans.append({
                        'SQL ID': row[0],
                        'Plan Hash': str(row[1]),
                        'Schema': row[2],
                        'Module': row[3],
                        'Executions': row[4],
                        'Elapsed (s)': float(row[5] or 0),
                        'Buffer Gets': row[6],
                        'Disk Reads': row[7],
                        'Rows': row[8],
                        'Last Active': row[9],
                        'SQL Text': text[:500],
                        'SQL Text Full': text
                    })
            finally:
                cursor.close()
            return plans
        except oracledb.Error as e:
            st.error(f"Error getting plan churn data: {e}")
            return []
    # --- END: get_plan_churn ---

    # --- START: get_resource_limits ---
    def get_resource_limits(self) -> Dict:
        """Fetch PGA/SGA utilization from v$resource_limit"""
        if not self.connection:
            return {}

        try:
            cursor = self.connection.cursor()
            try:
                query = """
                    SELECT resource_name, current_utilization, limit_value
                    FROM v$resource_limit
                    WHERE resource_name IN (
                        'processes',
                        'sessions',
                        'pga_aggregate_target',
                        'sga_target'
                    )
                """
                cursor.execute(query)
                limits = {}
                for name, current, limit_value in cursor:
                    limits[name] = {
                        'current': current,
                        'limit': limit_value
                    }
            finally:
                cursor.close()
            return limits
        except oracledb.Error:
            return {}
    # --- END: get_resource_limits ---
    
    # --- START: _log_app_event ---
    def _log_app_event(self, event_type: str, message: str, details: Dict = None):
        """Log application events"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,  # 'connect', 'disconnect', 'monitor_start', 'monitor_stop', 'error'
            'message': message,
            'details': details or {}
        }
        app_logger.info(f"{event_type.upper()}: {message}")
        
        # Also write structured JSON to app log
        app_log_file = self.log_dir / 'app_events.jsonl'
        try:
            with open(app_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            app_logger.error(f"Failed to write app event log: {e}")
    # --- END: _log_app_event ---
        
    # --- START: load_config ---
    def load_config(self, config_dict: Dict) -> bool:
        """Load configuration"""
        try:
            self.config = config_dict
            return True
        except Exception as e:
            st.error(f"Error loading configuration: {e}")
            return False
    # --- END: load_config ---
    
    # --- START: connect ---
    def connect(self, config: Dict) -> bool:
        """Establish connection to Oracle database"""
        try:
            db_config = config['database']
            dsn = oracledb.makedsn(
                db_config['host'],
                db_config['port'],
                service_name=db_config['service_name']
            )
            
            self.connection = oracledb.connect(
                user=db_config['username'],
                password=db_config['password'],
                dsn=dsn
            )
            
            st.session_state.connection = self.connection
            # Log connection without sensitive information
            self._log_app_event('connect', 
                               f"Connected to {db_config['host']}:{db_config['port']}/{db_config['service_name']}",
                               {'host': db_config['host'], 'port': db_config['port'], 
                                'service_name': db_config['service_name']})
            return True
        except oracledb.Error as e:
            error_msg = f"Failed to connect to Oracle database: {e}"
            st.error(error_msg)
            self._log_app_event('error', error_msg, {'error_type': 'connection_error', 'error': str(e)})
            return False
    # --- END: connect ---
    
    # --- START: disconnect ---
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self._log_app_event('disconnect', "Database connection closed")
            self.connection.close()
            self.connection = None
            st.session_state.connection = None
    # --- END: disconnect ---
    
    # --- START: _get_statistic_id ---
    def _get_statistic_id(self, cursor: oracledb.Cursor, stat_name: str) -> Optional[int]:
        """Get statistic ID from v$statname - READ ONLY"""
        try:
            cursor.execute(
                "SELECT statistic# FROM v$statname WHERE name = :name",
                name=stat_name
            )
            result = cursor.fetchone()
            return result[0] if result else None
        except oracledb.Error:
            return None
    # --- END: _get_statistic_id ---
    
    # --- START: get_session_overview ---
    def get_session_overview(self) -> Dict:
        """Get current session overview - READ ONLY"""
        if not self.connection:
            return {}
        
        try:
            cursor = self.connection.cursor()
            try:
                # Get statistic IDs
                stat_logical = self._get_statistic_id(cursor, 'session logical reads')
                stat_physical = self._get_statistic_id(cursor, 'physical reads')
                stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')
                
                if not all([stat_logical, stat_physical, stat_cpu]):
                    return {}
                
                # Main query - READ ONLY (SELECT only, no data modification)
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
            finally:
                cursor.close()
            
            if row:
                return {
                    'timestamp': datetime.now(),
                    'total_sessions': row[0] or 0,
                    'active_sessions': row[1] or 0,
                    'inactive_sessions': row[2] or 0,
                    'blocked_sessions': row[3] or 0,
                    'logical_reads_mb': float(row[4] or 0),
                    'physical_reads_mb': float(row[5] or 0),
                    'cpu_seconds': float(row[6] or 0)
                }
            return {}
            
        except oracledb.Error as e:
            st.error(f"Error getting session overview: {e}")
            return {}
    # --- END: get_session_overview ---
    
    # --- START: get_top_sessions ---
    def get_top_sessions(self, limit: int = 10) -> List[Dict]:
        """Get top resource-consuming sessions - READ ONLY"""
        if not self.connection:
            return []

        try:
            cursor = self.connection.cursor()
            try:
                stat_logical = self._get_statistic_id(cursor, 'session logical reads')
                stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')
                
                if not all([stat_logical, stat_cpu]):
                    return []
                
                # READ ONLY query (SELECT only, no data modification)
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
                        q.sql_text,
                        q.plan_hash_value,
                        q.module,
                        q.action
                    FROM v$session s
                    LEFT JOIN v$sesstat stat ON s.sid = stat.sid 
                        AND stat.statistic# IN (:stat_logical, :stat_cpu)
                    LEFT JOIN v$sql q ON s.sql_id = q.sql_id
                    WHERE s.username IS NOT NULL
                    GROUP BY s.sid, s.serial#, s.username, s.program, s.status, s.event, s.sql_id,
                             q.sql_text, q.plan_hash_value, q.module, q.action
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
                    full_sql = (row[9] or '').strip()
                    sessions.append({
                        'SID': row[0],
                        'Serial#': row[1],
                        'Username': row[2] or 'N/A',
                        'Program': row[3] or 'N/A',
                        'Status': row[4] or 'N/A',
                        'Logical Reads (MB)': float(row[5] or 0),
                        'CPU (seconds)': float(row[6] or 0),
                        'Wait Event': row[7] or 'N/A',
                        'SQL ID': row[8] or 'N/A',
                        'SQL Text': full_sql[:500],
                        'SQL Text Full': full_sql,
                        'Plan Hash': str(row[10]) if row[10] is not None else 'N/A',
                        'Module': row[11] or 'N/A',
                        'Action': row[12] or 'N/A'
                    })
            finally:
                cursor.close()
            
            total_cpu = sum(item['CPU (seconds)'] for item in sessions) or 0
            if total_cpu > 0:
                for item in sessions:
                    item['CPU %'] = round((item['CPU (seconds)'] / total_cpu) * 100, 2)
            else:
                for item in sessions:
                    item['CPU %'] = 0.0

            return sessions
            
        except oracledb.Error as e:
            st.error(f"Error getting top sessions: {e}")
            return []
    # --- END: get_top_sessions ---

    # --- START: get_top_cpu_sessions ---
    def get_top_cpu_sessions(self, limit: int = 10) -> List[Dict]:
        """Get sessions consuming the most CPU, including SQL text - READ ONLY"""
        if not self.connection:
            return []

        try:
            cursor = self.connection.cursor()
            try:
                stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')

                if not stat_cpu:
                    return []

                query = """
                    SELECT
                        s.sid,
                        s.serial#,
                        s.username,
                        s.program,
                        s.machine,
                        s.status,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_cpu THEN stat.value ELSE 0 END) / 100, 2) AS cpu_seconds,
                        s.sql_id,
                        q.sql_text,
                        q.plan_hash_value,
                        q.module,
                        q.action
                    FROM v$session s
                    LEFT JOIN v$sesstat stat ON s.sid = stat.sid
                        AND stat.statistic# = :stat_cpu
                    LEFT JOIN v$sql q ON s.sql_id = q.sql_id
                    WHERE s.username IS NOT NULL
                    GROUP BY s.sid, s.serial#, s.username, s.program, s.machine, s.status, s.sql_id,
                             q.sql_text, q.plan_hash_value, q.module, q.action
                    ORDER BY MAX(CASE WHEN stat.statistic# = :stat_cpu THEN stat.value ELSE 0 END) DESC
                    FETCH FIRST :limit ROWS ONLY
                """

                cursor.execute(query, {
                    'stat_cpu': stat_cpu,
                    'limit': limit
                })

                sessions = []
                for row in cursor:
                    full_sql = (row[8] or '').strip()
                    sessions.append({
                        'SID': row[0],
                        'Serial#': row[1],
                        'Username': row[2] or 'N/A',
                        'Program': row[3] or 'N/A',
                        'Machine': row[4] or 'N/A',
                        'Status': row[5] or 'N/A',
                        'CPU (seconds)': float(row[6] or 0),
                        'SQL ID': row[7] or 'N/A',
                        'SQL Text': full_sql[:500],
                        'SQL Text Full': full_sql,
                        'Plan Hash': str(row[9]) if row[9] is not None else 'N/A',
                        'Module': row[10] or 'N/A',
                        'Action': row[11] or 'N/A'
                    })
            finally:
                cursor.close()
            
            total_cpu = sum(item['CPU (seconds)'] for item in sessions) or 0
            if total_cpu > 0:
                for item in sessions:
                    item['CPU %'] = round((item['CPU (seconds)'] / total_cpu) * 100, 2)
            else:
                for item in sessions:
                    item['CPU %'] = 0.0

            return sessions

        except oracledb.Error as e:
            st.error(f"Error getting top CPU sessions: {e}")
            return []
    # --- END: get_top_cpu_sessions ---
    
    # --- START: get_blocking_sessions ---
    def get_blocking_sessions(self) -> List[Dict]:
        """Get blocking sessions information - READ ONLY"""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            try:
                # READ ONLY query (SELECT only, no data modification)
                query = """
                    SELECT 
                        blocking.sid AS blocking_sid,
                        blocking.serial# AS blocking_serial#,
                        blocking.username AS blocking_user,
                        blocking.program AS blocking_program,
                        blocked.sid AS blocked_sid,
                        blocked.serial# AS blocked_serial#,
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
                        'Blocking SID': row[0],
                        'Blocking Serial#': row[1],
                        'Blocking User': row[2] or 'N/A',
                        'Blocking Program': row[3] or 'N/A',
                        'Blocked SID': row[4],
                        'Blocked Serial#': row[5],
                        'Blocked User': row[6] or 'N/A',
                        'Blocked Program': row[7] or 'N/A',
                        'Wait Event': row[8] or 'N/A',
                        'Wait Seconds': row[9] or 0
                    })
            finally:
                cursor.close()
            return blocking_info
            
        except oracledb.Error as e:
            st.error(f"Error getting blocking sessions: {e}")
            return []
    # --- END: get_blocking_sessions ---
    
    # --- START: get_session_by_status ---
    def get_session_by_status(self) -> Dict:
        """Get session count by status - READ ONLY"""
        if not self.connection:
            return {}
        
        try:
            cursor = self.connection.cursor()
            try:
                # READ ONLY query (SELECT only, no data modification)
                query = """
                    SELECT status, COUNT(*) as count
                    FROM v$session
                    WHERE username IS NOT NULL
                    GROUP BY status
                """
                cursor.execute(query)
                
                status_data = {}
                for row in cursor:
                    status_data[row[0]] = row[1]
            finally:
                cursor.close()
            return status_data
            
        except oracledb.Error:
            return {}
    # --- END: get_session_by_status ---

    # --- START: get_all_sessions_traffic ---
    def get_all_sessions_traffic(self) -> List[Dict]:
        """Get all active and inactive sessions with traffic details - READ ONLY"""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            try:
                # READ ONLY query to get all sessions with their traffic metrics
                stat_logical = self._get_statistic_id(cursor, 'session logical reads')
                stat_physical = self._get_statistic_id(cursor, 'physical reads')
                stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')
                
                query = """
                    SELECT 
                        s.sid,
                        s.serial#,
                        s.username,
                        s.program,
                        s.machine,
                        s.status,
                        s.logon_time,
                        s.last_call_et,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_logical THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS logical_reads_mb,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_physical THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS physical_reads_mb,
                        ROUND(MAX(CASE WHEN stat.statistic# = :stat_cpu THEN stat.value ELSE 0 END) / 100, 2) AS cpu_seconds,
                        s.event,
                        s.wait_time,
                        s.seconds_in_wait,
                        s.sql_id,
                        s.blocking_session,
                        p.spid AS os_process
                    FROM v$session s
                    LEFT JOIN v$sesstat stat ON s.sid = stat.sid
                        AND stat.statistic# IN (:stat_logical, :stat_physical, :stat_cpu)
                    LEFT JOIN v$process p ON s.paddr = p.addr
                    WHERE s.username IS NOT NULL
                    GROUP BY s.sid, s.serial#, s.username, s.program, s.machine, s.status, 
                             s.logon_time, s.last_call_et, s.event, s.wait_time, s.seconds_in_wait, 
                             s.sql_id, s.blocking_session, p.spid
                    ORDER BY s.status DESC, logical_reads_mb DESC
                """
                
                cursor.execute(query, {
                    'stat_logical': stat_logical,
                    'stat_physical': stat_physical,
                    'stat_cpu': stat_cpu
                })
                
                sessions = []
                for row in cursor:
                    sessions.append({
                        'SID': row[0],
                        'Serial#': row[1],
                        'Username': row[2] or 'N/A',
                        'Program': row[3] or 'N/A',
                        'Machine': row[4] or 'N/A',
                        'Status': row[5] or 'N/A',
                        'Logon Time': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else 'N/A',
                        'Last Call (sec)': row[7] or 0,
                        'Logical Reads (MB)': float(row[8] or 0),
                        'Physical Reads (MB)': float(row[9] or 0),
                        'CPU (seconds)': float(row[10] or 0),
                        'Wait Event': row[11] or 'N/A',
                        'Wait Time': row[12] or 0,
                        'Seconds in Wait': row[13] or 0,
                        'SQL ID': row[14] or 'N/A',
                        'Blocking Session': row[15] or None,
                        'OS Process': row[16] or 'N/A'
                    })
            finally:
                cursor.close()
            
            return sessions
            
        except oracledb.Error as e:
            st.error(f"Error getting session traffic: {e}")
            return []
    # --- END: get_all_sessions_traffic ---

    # --- START: get_sessions_grouped_by_traffic ---
    def get_sessions_grouped_by_traffic(self) -> List[Dict]:
        """Group sessions by user and program to identify high traffic sources - READ ONLY"""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            try:
                # READ ONLY query to group sessions and aggregate metrics
                stat_logical = self._get_statistic_id(cursor, 'session logical reads')
                stat_physical = self._get_statistic_id(cursor, 'physical reads')
                stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')
                
                query = """
                    SELECT 
                        s.username,
                        s.program,
                        s.status,
                        COUNT(*) AS session_count,
                        COUNT(CASE WHEN s.status = 'ACTIVE' THEN 1 END) AS active_count,
                        COUNT(CASE WHEN s.status = 'INACTIVE' THEN 1 END) AS inactive_count,
                        ROUND(SUM(CASE WHEN stat.statistic# = :stat_logical THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS total_logical_reads_mb,
                        ROUND(SUM(CASE WHEN stat.statistic# = :stat_physical THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS total_physical_reads_mb,
                        ROUND(SUM(CASE WHEN stat.statistic# = :stat_cpu THEN stat.value ELSE 0 END) / 100, 2) AS total_cpu_seconds,
                        COUNT(DISTINCT s.machine) AS machine_count,
                        COUNT(CASE WHEN s.blocking_session IS NOT NULL THEN 1 END) AS blocked_count
                    FROM v$session s
                    LEFT JOIN v$sesstat stat ON s.sid = stat.sid
                        AND stat.statistic# IN (:stat_logical, :stat_physical, :stat_cpu)
                    WHERE s.username IS NOT NULL
                    GROUP BY s.username, s.program, s.status
                    ORDER BY total_logical_reads_mb DESC, total_cpu_seconds DESC
                """
                
                cursor.execute(query, {
                    'stat_logical': stat_logical,
                    'stat_physical': stat_physical,
                    'stat_cpu': stat_cpu
                })
                
                grouped = []
                for row in cursor:
                    grouped.append({
                        'Username': row[0] or 'N/A',
                        'Program': row[1] or 'N/A',
                        'Status': row[2] or 'N/A',
                        'Total Sessions': row[3] or 0,
                        'Active Sessions': row[4] or 0,
                        'Inactive Sessions': row[5] or 0,
                        'Total Logical Reads (MB)': float(row[6] or 0),
                        'Total Physical Reads (MB)': float(row[7] or 0),
                        'Total CPU (seconds)': float(row[8] or 0),
                        'Machines': row[9] or 0,
                        'Blocked Sessions': row[10] or 0
                    })
            finally:
                cursor.close()
            
            return grouped
            
        except oracledb.Error as e:
            st.error(f"Error getting grouped session traffic: {e}")
            return []
    # --- END: get_sessions_grouped_by_traffic ---

    # --- START: get_tablespace_usage ---
    def get_tablespace_usage(self) -> List[Dict]:
        """Fetch tablespace utilization including auto-extend capacity - READ ONLY"""
        if not self.connection:
            return []

        try:
            cursor = self.connection.cursor()
            try:
                query = """
                    WITH file_stats AS (
                        SELECT tablespace_name,
                               SUM(bytes) AS current_bytes,
                               SUM(CASE WHEN autoextensible = 'YES' THEN maxbytes ELSE bytes END) AS max_bytes,
                               SUM(CASE WHEN autoextensible = 'YES' THEN maxbytes - bytes ELSE 0 END) AS autoextend_bytes,
                               COUNT(*) AS file_count,
                               SUM(CASE WHEN autoextensible = 'YES' THEN 1 ELSE 0 END) AS auto_file_count
                        FROM (
                            SELECT tablespace_name, bytes, autoextensible, maxbytes
                            FROM dba_data_files
                            UNION ALL
                            SELECT tablespace_name, bytes, autoextensible, maxbytes
                            FROM dba_temp_files
                        )
                        GROUP BY tablespace_name
                    )
                    SELECT
                        t.tablespace_name,
                        t.contents,
                        t.status,
                        t.block_size,
                        NVL(u.used_space, 0) AS used_blocks,
                        NVL(u.tablespace_size, 0) AS size_blocks,
                        NVL(fs.current_bytes, 0) AS current_bytes,
                        NVL(fs.max_bytes, NVL(fs.current_bytes, 0)) AS max_bytes,
                        NVL(fs.autoextend_bytes, 0) AS autoextend_bytes,
                        NVL(fs.file_count, 0) AS file_count,
                        NVL(fs.auto_file_count, 0) AS auto_file_count
                    FROM dba_tablespaces t
                    LEFT JOIN dba_tablespace_usage_metrics u
                        ON t.tablespace_name = u.tablespace_name
                    LEFT JOIN file_stats fs
                        ON t.tablespace_name = fs.tablespace_name
                    ORDER BY t.tablespace_name
                """
                cursor.execute(query)
                tablespaces = []
                for row in cursor:
                    block_size = row[3] or 0
                    used_blocks = row[4] or 0
                    size_blocks = row[5] or 0
                    current_bytes = row[6] or 0
                    max_bytes = row[7] or current_bytes
                    auto_bytes = row[8] or 0
                    file_count = int(row[9] or 0)
                    auto_file_count = int(row[10] or 0)

                    used_bytes = used_blocks * block_size
                    allocated_bytes = size_blocks * block_size
                    capacity_bytes = max(max_bytes, allocated_bytes, current_bytes)
                    if capacity_bytes == 0:
                        capacity_bytes = max(current_bytes, allocated_bytes)
                    pct_used = round((used_bytes / capacity_bytes) * 100, 2) if capacity_bytes else 0.0

                    tablespaces.append({
                        'Tablespace': row[0],
                        'Type': row[1] or 'N/A',
                        'Status': row[2] or 'N/A',
                        'Used MB': round(used_bytes / (1024 ** 2), 2),
                        'Allocated MB': round(allocated_bytes / (1024 ** 2), 2),
                        'Max MB': round(capacity_bytes / (1024 ** 2), 2),
                        'Free MB': round(max(capacity_bytes - used_bytes, 0) / (1024 ** 2), 2),
                        'Pct Used': pct_used,
                        'Autoextend Headroom MB': round(auto_bytes / (1024 ** 2), 2),
                        'Files': file_count,
                        'Autoextend Files': auto_file_count,
                        'Autoextend Capable': auto_file_count > 0
                    })
            finally:
                cursor.close()
            return tablespaces
        except oracledb.Error as e:
            st.error(f"Error getting tablespace usage: {e}")
            return []
    # --- END: get_tablespace_usage ---


# --- START: main ---
def main():
    """Main Streamlit application"""
    
    # Title
    st.title("📊 Oracle Database Session Monitor")
    st.markdown("**Read-only monitoring tool for Oracle 19+ databases**")
    
    # Load default configuration
    config_defaults = {
        'database': {
            'host': 'localhost',
            'port': 1521,
            'service_name': 'ORCL',
            'username': '',
            'password': ''
        },
        'monitoring': {
            'interval_seconds': 60,
            'alert_thresholds': {
                'max_sessions': 500,
                'max_active_sessions': 200,
                'max_blocked_sessions': 10,
                'max_tablespace_pct': 90
            }
        }
    }
    if 'config_defaults' not in st.session_state:
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                if 'database' in loaded_config:
                    config_defaults['database'].update(loaded_config['database'])
                if 'monitoring' in loaded_config:
                    monitoring_loaded = loaded_config['monitoring']
                    config_defaults['monitoring'].update(monitoring_loaded)
                    if 'alert_thresholds' in monitoring_loaded:
                        config_defaults['monitoring']['alert_thresholds'].update(
                            monitoring_loaded['alert_thresholds']
                        )
        except FileNotFoundError:
            pass
        except json.JSONDecodeError as e:
            st.warning(f"Invalid JSON in config.json: {e}")
        st.session_state.config_defaults = config_defaults.copy()
    else:
        config_defaults = st.session_state.config_defaults
    
    # Sidebar - Configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Database connection form
        with st.form("db_config"):
            st.subheader("Database Connection")
            db_host = st.text_input("Host", value=config_defaults['database'].get('host', 'localhost'))
            db_port = st.number_input(
                "Port",
                value=int(config_defaults['database'].get('port', 1521)),
                min_value=1,
                max_value=65535
            )
            db_service = st.text_input("Service Name", value=config_defaults['database'].get('service_name', 'ORCL'))
            db_username = st.text_input("Username", value=config_defaults['database'].get('username', ''), type="default")
            db_password = st.text_input("Password", value=config_defaults['database'].get('password', ''), type="password")
            
            connect_button = st.form_submit_button("🔌 Connect", width='stretch')
        
        if connect_button:
            config = {
                'database': {
                    'host': db_host,
                    'port': int(db_port),
                    'service_name': db_service,
                    'username': db_username,
                    'password': db_password
                },
                'monitoring': {
                    'interval_seconds': 5,
                    'alert_thresholds': {
                        'max_sessions': 500,
                        'max_active_sessions': 200,
                        'max_blocked_sessions': 10,
                        'max_tablespace_pct': 90
                    }
                }
            }
            
            st.session_state.config_defaults['database'] = config['database']
            st.session_state.config_defaults['monitoring'] = config['monitoring']
            
            monitor = OracleMonitorGUI()
            if monitor.load_config(config):
                if monitor.connect(config):
                    st.session_state.monitor = monitor
                    st.session_state.config = config
                    st.success("✅ Connected successfully!")
                    st.rerun()
        
        st.divider()
        
        # Monitoring controls
        if 'monitor' in st.session_state:
            st.subheader("📡 Monitoring Controls")
            interval_options = [3, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600]
            default_interval = 60
            config_interval = st.session_state.config['monitoring'].get('interval_seconds', default_interval)
            if 'refresh_interval' not in st.session_state:
                st.session_state.refresh_interval = config_interval or default_interval
            current_interval = st.session_state.get('refresh_interval', default_interval)

            interval_index = interval_options.index(current_interval) if current_interval in interval_options else 1
            selected_interval = st.selectbox(
                "Auto-refresh interval (seconds)",
                options=interval_options,
                index=interval_index,
                help="Controls how often the dashboard auto-refreshes while monitoring."
            )
            st.session_state.refresh_interval = selected_interval
            
            if st.button("▶️ Start Monitoring", width='stretch', disabled=st.session_state.monitoring):
                st.session_state.monitoring = True
                st.session_state.history = []
                if 'monitor' in st.session_state:
                    st.session_state.monitor._log_app_event('monitor_start', "Monitoring started")
                st.rerun()
            
            if st.button("⏸️ Stop Monitoring", width='stretch', disabled=not st.session_state.monitoring):
                st.session_state.monitoring = False
                if 'monitor' in st.session_state:
                    st.session_state.monitor._log_app_event('monitor_stop', "Monitoring stopped")
                st.rerun()
            
            if st.button("🔄 Refresh Now", width='stretch'):
                st.rerun()
            
            if st.button("🗑️ Clear History", width='stretch'):
                st.session_state.history = []
                st.rerun()
            
            if st.button("🔌 Disconnect", width='stretch'):
                if 'monitor' in st.session_state:
                    st.session_state.monitor.disconnect()
                st.session_state.monitoring = False
                st.session_state.connection = None
                if 'monitor' in st.session_state:
                    del st.session_state.monitor
                st.rerun()
    
    # Main content area
    if 'monitor' not in st.session_state or st.session_state.connection is None:
        st.info("👈 Please configure and connect to database in the sidebar")
        st.markdown("""
        ### Features:
        - ✅ **Read-only monitoring** - No data modification
        - 📊 **Real-time dashboards** - Live session metrics
        - 🚨 **Alert system** - Configurable thresholds
        - 📈 **Historical charts** - Trend analysis
        - 🔍 **Top sessions** - Resource consumption tracking
        - 🔒 **Blocking detection** - Identify session conflicts
        """)
    else:
        monitor = st.session_state.monitor
        
        # Get current data
        overview = monitor.get_session_overview()
        alerts = []  # Initialize alerts list
        
        if overview:
            # Check for alerts
            monitoring_cfg = st.session_state.config.get('monitoring', {})
            thresholds = monitoring_cfg.get('alert_thresholds', {})
            host_metrics = monitor.get_host_metrics()
            resource_limits = monitor.get_resource_limits()
            interval_seconds = st.session_state.get(
                'refresh_interval',
                monitoring_cfg.get('interval_seconds', 60)
            )
            sample_id = datetime.now(timezone.utc).isoformat()
            overview_for_log = dict(overview)
            overview_ts = overview_for_log.get('timestamp')
            if isinstance(overview_ts, datetime):
                overview_for_log['timestamp'] = overview_ts.isoformat()
            sample_meta = {
                'sample_id': sample_id,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'interval_seconds': interval_seconds,
                'overview': overview_for_log,
                'host_metrics': host_metrics,
                'resource_limits': resource_limits,
                'thresholds': thresholds
            }
            io_sessions = monitor.get_io_sessions(20)
            if io_sessions:
                monitor._log_io_sessions(io_sessions, sample_meta=sample_meta)
            else:
                io_sessions = []
            wait_events = monitor.get_wait_events(10)
            if wait_events:
                monitor._log_wait_events(wait_events, sample_meta=sample_meta)
                if monitor.history_store:
                    monitor.history_store.insert_wait_events(sample_id, sample_meta['generated_at'], wait_events)
            else:
                wait_events = []
            temp_usage = monitor.get_temp_usage(15)
            undo_metrics = monitor.get_undo_metrics()
            if temp_usage or undo_metrics:
                monitor._log_temp_usage(temp_usage, undo_metrics, sample_meta=sample_meta)
                if monitor.history_store:
                    if temp_usage:
                        monitor.history_store.insert_temp_usage(sample_id, sample_meta['generated_at'], temp_usage)
                    if undo_metrics:
                        monitor.history_store.insert_undo_metrics(sample_id, sample_meta['generated_at'], undo_metrics)
            if not temp_usage:
                temp_usage = []
            if not undo_metrics:
                undo_metrics = {}
            redo_metrics = monitor.get_redo_metrics()
            if redo_metrics:
                monitor._log_redo_metrics(redo_metrics, sample_meta=sample_meta)
                if monitor.history_store:
                    monitor.history_store.insert_redo_metrics(sample_id, sample_meta['generated_at'], redo_metrics)
            else:
                redo_metrics = {}
            plan_churn = monitor.get_plan_churn(15)
            if plan_churn:
                monitor._log_plan_churn(plan_churn, sample_meta=sample_meta)
                if monitor.history_store:
                    monitor.history_store.insert_plan_history(sample_id, sample_meta['generated_at'], plan_churn)
            else:
                plan_churn = []
            
            # Store traffic metrics
            all_traffic = monitor.get_all_sessions_traffic()
            if all_traffic:
                monitor._log_traffic_sessions(all_traffic, sample_meta=sample_meta)
                if monitor.history_store:
                    monitor.history_store.insert_all_sessions_traffic(sample_id, sample_meta['generated_at'], all_traffic)
            
            grouped_traffic = monitor.get_sessions_grouped_by_traffic()
            if grouped_traffic:
                monitor._log_grouped_traffic(grouped_traffic, sample_meta=sample_meta)
                if monitor.history_store:
                    monitor.history_store.insert_grouped_traffic(sample_id, sample_meta['generated_at'], grouped_traffic)
            
            blocking_chains = monitor.get_blocking_chains()
            if not blocking_chains:
                blocking_chains = []
            
            if overview.get('total_sessions', 0) >= thresholds['max_sessions']:
                alert_msg = f"Total sessions ({overview['total_sessions']}) exceeds threshold ({thresholds['max_sessions']})"
                alerts.append(alert_msg)
                monitor._log_alert('warning', alert_msg, {
                    'metric': 'total_sessions',
                    'value': overview['total_sessions'],
                    'threshold': thresholds['max_sessions']
                })
            
            if overview.get('active_sessions', 0) >= thresholds['max_active_sessions']:
                alert_msg = f"Active sessions ({overview['active_sessions']}) exceeds threshold ({thresholds['max_active_sessions']})"
                alerts.append(alert_msg)
                monitor._log_alert('warning', alert_msg, {
                    'metric': 'active_sessions',
                    'value': overview['active_sessions'],
                    'threshold': thresholds['max_active_sessions']
                })
            
            if overview.get('blocked_sessions', 0) >= thresholds['max_blocked_sessions']:
                alert_msg = f"Blocked sessions ({overview['blocked_sessions']}) exceeds threshold ({thresholds['max_blocked_sessions']})"
                alerts.append(alert_msg)
                monitor._log_alert('critical', alert_msg, {
                    'metric': 'blocked_sessions',
                    'value': overview['blocked_sessions'],
                    'threshold': thresholds['max_blocked_sessions']
                })
            
            # Log metrics
            overview['alert_count'] = len(alerts)
            monitor._log_metrics_json(
                overview,
                sample_meta=sample_meta,
                host_metrics=host_metrics,
                resource_limits=resource_limits
            )
            monitor._log_metrics_csv(
                overview,
                sample_meta=sample_meta,
                host_metrics=host_metrics
            )
            
            # Add to history if monitoring
            if st.session_state.monitoring:
                st.session_state.history.append(overview)
                # Keep only last 100 records
                if len(st.session_state.history) > 100:
                    st.session_state.history = st.session_state.history[-100:]
            
            # Key Metrics Row
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Sessions", overview['total_sessions'], 
                         delta=None if not st.session_state.history else 
                         overview['total_sessions'] - st.session_state.history[-1]['total_sessions'] 
                         if len(st.session_state.history) > 1 else None)
            
            with col2:
                st.metric("Active Sessions", overview['active_sessions'],
                         delta=None if not st.session_state.history else 
                         overview['active_sessions'] - st.session_state.history[-1]['active_sessions']
                         if len(st.session_state.history) > 1 else None)
            
            with col3:
                st.metric("Blocked Sessions", overview['blocked_sessions'],
                         delta=None, 
                         delta_color="inverse" if overview['blocked_sessions'] > 0 else "normal")
            
            with col4:
                st.metric("CPU Time (s)", f"{overview['cpu_seconds']:.2f}")
            
            # Charts Row
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Session Status Distribution")
                status_data = monitor.get_session_by_status()
                if status_data:
                    fig_pie = px.pie(
                        values=list(status_data.values()),
                        names=list(status_data.keys()),
                        title="Sessions by Status"
                    )
                    st.plotly_chart(fig_pie, width='stretch')
                else:
                    st.info("No status data available")
            
            with col2:
                st.subheader("📈 Resource Usage")
                resource_data = {
                    'Logical Reads (MB)': overview['logical_reads_mb'],
                    'Physical Reads (MB)': overview['physical_reads_mb']
                }
                fig_bar = px.bar(
                    x=list(resource_data.keys()),
                    y=list(resource_data.values()),
                    title="I/O Statistics"
                )
                st.plotly_chart(fig_bar, width='stretch')
            
            # Historical Chart
            if len(st.session_state.history) > 1:
                st.subheader("📉 Historical Trends")
                df_history = pd.DataFrame(st.session_state.history)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig_sessions = px.line(
                        df_history,
                        x='timestamp',
                        y=['total_sessions', 'active_sessions'],
                        title="Session Count Over Time",
                        labels={'value': 'Count', 'timestamp': 'Time'}
                    )
                    st.plotly_chart(fig_sessions, width='stretch')
                
                with col2:
                    fig_resources = px.line(
                        df_history,
                        x='timestamp',
                        y=['logical_reads_mb', 'physical_reads_mb'],
                        title="I/O Over Time",
                        labels={'value': 'MB', 'timestamp': 'Time'}
                    )
                    st.plotly_chart(fig_resources, width='stretch')

            # Host metrics cards
            if host_metrics:
                st.subheader("🖥️ Host Metrics")
                hcol1, hcol2, hcol3 = st.columns(3)
                with hcol1:
                    st.metric(
                        "CPU Usage",
                        f"{host_metrics['cpu_percent']:.1f}%",
                        help=f"Logical cores: {host_metrics['cpu_count']}"
                    )
                with hcol2:
                    st.metric(
                        "Memory Usage",
                        f"{host_metrics['memory_percent']:.1f}%",
                        help=f"{host_metrics['memory_used_gb']:.2f} / {host_metrics['memory_total_gb']:.2f} GB"
                    )
                with hcol3:
                    st.metric(
                        "Process CPU",
                        f"{host_metrics['process_cpu_percent']:.1f}%",
                        help=f"Agent RSS: {host_metrics['process_memory_mb']:.1f} MB"
                    )
            
            # Tabs for detailed information
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13, tab14, tab15, tab16 = st.tabs([
                "🔝 Top Sessions",
                "🔥 High CPU Sessions",
                "👥 Grouped Sessions",
                "🧠 Resource Usage",
                "🔒 Blocking Sessions",
                "📋 Current Overview",
                "🗄️ Tablespaces",
                "💾 Storage I/O",
                "⏱️ Wait Events",
                "🧊 Temp & Undo",
                "🟥 Redo/Log Writer",
                "🗂️ Plan Churn",
                "🖥️ Host Details",
                "🚦 All Sessions Traffic",
                "📊 Traffic by User/Program",
                "🗃️ SQLite History"
            ])
            
            with tab1:
                st.subheader("Top Resource-Consuming Sessions")
                top_sessions = monitor.get_top_sessions(20)
                if top_sessions:
                    df_top = pd.DataFrame(top_sessions)
                    st.dataframe(df_top, hide_index=True, width='stretch')
                    # Log top sessions
                    monitor._log_sessions(top_sessions, 'top', sample_meta=sample_meta)
                    sql_details = [s for s in top_sessions if s.get('SQL Text Full')]
                    if sql_details:
                        with st.expander("📜 Top Session SQL Texts"):
                            for sess in sql_details:
                                header = f"SID {sess['SID']} · SQL {sess.get('SQL ID', 'N/A')}"
                                st.markdown(f"**{header}**  \nUser: {sess['Username']} · Program: {sess['Program']}")
                                st.code(sess.get('SQL Text Full') or 'N/A', language='sql')
                else:
                    st.info("No session data available")
            
            with tab2:
                st.subheader("High CPU Sessions")
                high_cpu_sessions = monitor.get_top_cpu_sessions(15)
                if high_cpu_sessions:
                    df_cpu = pd.DataFrame(high_cpu_sessions)
                    st.dataframe(df_cpu, hide_index=True, width='stretch')
                    monitor._log_sessions(high_cpu_sessions, 'cpu', sample_meta=sample_meta)
                    sql_details = [s for s in high_cpu_sessions if s.get('SQL Text Full')]
                    if sql_details:
                        with st.expander("🔥 CPU Session SQL Texts"):
                            for sess in sql_details:
                                header = f"SID {sess['SID']} · SQL {sess.get('SQL ID', 'N/A')}"
                                st.markdown(f"**{header}**  \nUser: {sess['Username']} · Program: {sess['Program']}")
                                st.code(sess.get('SQL Text Full') or 'N/A', language='sql')
                else:
                    st.info("No CPU intensive sessions detected")

            with tab3:
                st.subheader("Grouped Sessions")
                grouping_mode = st.selectbox(
                    "Group by",
                    ["user_program", "user", "program", "sql", "module"],
                    format_func=lambda x: {
                        "user_program": "Username + Program",
                        "user": "Username",
                        "program": "Program",
                        "sql": "SQL ID",
                        "module": "Module"
                    }[x]
                )
                grouped_sessions = monitor.group_sessions(
                    monitor.get_top_sessions(50) +
                    monitor.get_top_cpu_sessions(50) +
                    monitor.get_session_resource_usage(50),
                    grouping_mode
                )
                if grouped_sessions:
                    df_grouped = pd.DataFrame(grouped_sessions)
                    st.dataframe(df_grouped, hide_index=True, width='stretch')
                    monitor._log_sessions(grouped_sessions, 'grouped', sample_meta=sample_meta, extra={'group_by': grouping_mode})

                    sql_groups = [g for g in grouped_sessions if g.get('Sample SQL Text')]
                    if sql_groups:
                        with st.expander("👥 Group SQL Texts"):
                            for grp in sql_groups:
                                header = f"{grp['Group Key']} · SQL {grp.get('Sample SQL ID', 'N/A')}"
                                st.markdown(f"**{header}**  \nSessions: {grp['Session Count']} · Total CPU: {grp['Total CPU (s)']:.2f}s")
                                st.code(grp['Sample SQL Text'], language='sql')
                else:
                    st.info("No grouped session data available")

            with tab4:
                st.subheader("Session Memory & Thread Usage")
                resource_sessions = monitor.get_session_resource_usage(15)
                if resource_sessions:
                    df_resource = pd.DataFrame(resource_sessions)
                    st.dataframe(df_resource, hide_index=True, width='stretch')
                    monitor._log_sessions(resource_sessions, 'resource', sample_meta=sample_meta)
                    sql_details = [s for s in resource_sessions if s.get('SQL Text Full')]
                    if sql_details:
                        with st.expander("🧠 Resource Session SQL Texts"):
                            for sess in sql_details:
                                header = f"SID {sess['SID']} · SQL {sess.get('SQL ID', 'N/A')}"
                                st.markdown(f"**{header}**  \nUser: {sess['Username']} · Program: {sess['Program']}")
                                st.code(sess.get('SQL Text Full') or 'N/A', language='sql')
                else:
                    st.info("No session resource data available")

                if resource_limits:
                    st.markdown("**Database Resource Limits**")
                    limit_rows = []
                    for name, values in resource_limits.items():
                        limit_rows.append({
                            'Resource': name,
                            'Current': values['current'],
                            'Limit': values['limit']
                        })
                    st.dataframe(pd.DataFrame(limit_rows), hide_index=True, width='stretch')

            with tab5:
                st.subheader("Blocking Sessions")
                blocking = monitor.get_blocking_sessions()
                if blocking:
                    df_blocking = pd.DataFrame(blocking)
                    st.dataframe(df_blocking, hide_index=True, width='stretch')
                    st.warning(f"⚠️ Found {len(blocking)} blocking session(s)")
                    # Log blocking sessions
                    monitor._log_sessions(blocking, 'blocking', sample_meta=sample_meta)
                    # Log alert for blocking
                    for block in blocking:
                        monitor._log_alert('critical', 
                                          f"Session {block['Blocking SID']} blocking {block['Blocked SID']}",
                                          block)
                    if blocking_chains:
                        st.markdown("**Blocking Chains**")
                        df_chain = pd.DataFrame(blocking_chains)
                        st.dataframe(df_chain, hide_index=True, width='stretch')
                        monitor._log_sessions(blocking_chains, 'blocking_chain', sample_meta=sample_meta)
                else:
                    st.success("✅ No blocking sessions detected")
            
            with tab6:
                st.subheader("Current Session Overview")
                overview_df = pd.DataFrame([overview])
                st.dataframe(overview_df, hide_index=True, width='stretch')
                
                # Export button
                if st.button("💾 Export History to CSV"):
                    if st.session_state.history:
                        df_export = pd.DataFrame(st.session_state.history)
                        csv = df_export.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name=f"oracle_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("No history to export")

            with tab7:
                st.subheader("Tablespace Usage")
                tablespaces = monitor.get_tablespace_usage()
                if tablespaces:
                    df_tablespaces = pd.DataFrame(tablespaces).sort_values('Pct Used', ascending=False)
                    st.dataframe(df_tablespaces, hide_index=True, width='stretch')

                    fig_tablespace = px.bar(
                        df_tablespaces,
                        x='Tablespace',
                        y='Pct Used',
                        color='Autoextend Capable',
                        title="Tablespace Utilization (%)",
                        labels={'Pct Used': 'Percent Used'}
                    )
                    st.plotly_chart(fig_tablespace, width='stretch')

                    monitor._log_tablespaces(tablespaces, sample_meta=sample_meta)

                    ts_threshold = thresholds.get('max_tablespace_pct', 90)
                    nearing_capacity = [ts for ts in tablespaces if ts['Pct Used'] >= ts_threshold]
                    if nearing_capacity:
                        for ts in nearing_capacity:
                            severity = 'critical' if ts['Pct Used'] >= (ts_threshold + 5) else 'warning'
                            message = (f"Tablespace {ts['Tablespace']} is {ts['Pct Used']:.2f}% used "
                                       f"(threshold {ts_threshold}%)")
                            st.warning(f"⚠️ {message}")
                            monitor._log_alert(
                                severity,
                                message,
                                {
                                    'tablespace': ts['Tablespace'],
                                    'pct_used': ts['Pct Used'],
                                    'max_threshold_pct': ts_threshold,
                                    'free_mb': ts['Free MB'],
                                    'autoextend_headroom_mb': ts['Autoextend Headroom MB'],
                                    'autoextend_capable': ts['Autoextend Capable']
                                }
                            )
                    else:
                        st.success("✅ All tablespaces are within safe utilization thresholds")
                else:
                    st.info("No tablespace data available (insufficient privileges or unsupported version).")

            with tab8:
                st.subheader("Storage I/O Sessions")
                if io_sessions:
                    df_io = pd.DataFrame(io_sessions)
                    st.dataframe(df_io, hide_index=True, width='stretch')

                    total_read_mb = sum(sess['Read MB'] for sess in io_sessions)
                    total_write_mb = sum(sess['Write MB'] for sess in io_sessions)
                    st.caption(f"Total Read: {total_read_mb:.2f} MB • Total Write: {total_write_mb:.2f} MB")

                    fig_io = px.bar(
                        df_io,
                        x='SID',
                        y=['Read MB', 'Write MB'],
                        barmode='group',
                        title="Top Storage I/O Sessions (MB)",
                        labels={'value': 'MB', 'SID': 'Session ID'}
                    )
                    st.plotly_chart(fig_io, width='stretch')

                    sql_details = [sess for sess in io_sessions if sess.get('SQL Text Full')]
                    if sql_details:
                        with st.expander("📜 Storage I/O SQL Texts"):
                            for sess in sql_details:
                                header = f"SID {sess['SID']} · SQL {sess.get('SQL ID', 'N/A')}"
                                st.markdown(
                                    f"**{header}**  \nUser: {sess['Username']} · Program: {sess['Program']} · "
                                    f"Reads: {sess['Read MB']:.2f}MB · Writes: {sess['Write MB']:.2f}MB"
                                )
                                st.code(sess.get('SQL Text Full') or 'N/A', language='sql')
                else:
                    st.success("No significant storage I/O detected for monitored sessions.")

            with tab9:
                st.subheader("Wait Event Profile")
                if wait_events:
                    df_waits = pd.DataFrame(wait_events)
                    st.dataframe(df_waits, hide_index=True, width='stretch')
                    fig_waits = px.bar(
                        df_waits,
                        x='Event',
                        y='Total Wait (s)',
                        color='Wait Class',
                        title="Top Wait Events",
                        labels={'Total Wait (s)': 'Seconds'}
                    )
                    st.plotly_chart(fig_waits, width='stretch')
                else:
                    st.info("No significant waits detected (non-idle).")

            with tab10:
                st.subheader("Temp & Undo Usage")
                if temp_usage:
                    df_temp = pd.DataFrame(temp_usage)
                    st.dataframe(df_temp, hide_index=True, width='stretch')
                    fig_temp = px.bar(
                        df_temp,
                        x='Tablespace',
                        y='Used MB',
                        color='Segment Type',
                        title="Temp Usage by Tablespace",
                        labels={'Used MB': 'MB'}
                    )
                    st.plotly_chart(fig_temp, width='stretch')
                else:
                    st.info("Temp usage is currently minimal.")

                if undo_metrics:
                    st.markdown("**Undo Metrics (Latest v$undostat sample)**")
                    ucol1, ucol2, ucol3 = st.columns(3)
                    ucol1.metric("Active Undo Blocks", undo_metrics.get('Undo Blocks', 'N/A'))
                    ucol2.metric("Transactions", undo_metrics.get('Transactions', 'N/A'))
                    ucol3.metric("Max Query (s)", undo_metrics.get('Max Query (s)', 'N/A'))
                    st.caption(
                        f"Tuned Retention: {undo_metrics.get('Tuned Retention (s)', 'N/A')}s • "
                        f"ORA-01555: {undo_metrics.get('ORA-01555 Errors', 'N/A')} • "
                        f"No-space: {undo_metrics.get('No Space Errors', 'N/A')} "
                        f"• Sample: {undo_metrics.get('Sample Time', 'N/A')}"
                    )
                else:
                    st.info("Undo statistics unavailable.")

            with tab11:
                st.subheader("Redo / Log Writer Metrics")
                if redo_metrics:
                    rcol1, rcol2, rcol3 = st.columns(3)
                    rcol1.metric("Redo Size (bytes)", redo_metrics.get('Redo Size (bytes)', 'N/A'))
                    rcol2.metric("Redo Writes", redo_metrics.get('Redo Writes', 'N/A'))
                    rcol3.metric("Redo Write Time (cs)", redo_metrics.get('Redo Write Time (cs)', 'N/A'))
                    st.metric("Log File Sync Waits", redo_metrics.get('Log File Sync Waits', 'N/A'))
                    st.metric("Log File Sync Time (ms)", redo_metrics.get('Log File Sync Time (ms)', 'N/A'))
                else:
                    st.info("Redo metrics unavailable.")

            with tab12:
                st.subheader("Plan Churn (Recent SQL)")
                plan_display = plan_churn
                plan_from_history = False
                if not plan_display and monitor.history_store:
                    plan_display = monitor.history_store.fetch_plan_history(20)
                    plan_from_history = bool(plan_display)

                if plan_display:
                    df_plan = pd.DataFrame(plan_display)
                    st.dataframe(df_plan, hide_index=True, width='stretch')
                    if plan_from_history:
                        st.caption("No live plan samples available; showing latest SQLite history instead.")
                    sql_details = [p for p in plan_display if p.get('SQL Text Full')]
                    if sql_details:
                        with st.expander("📄 SQL Texts (Plan Churn)"):
                            for plan in sql_details:
                                header = f"{plan.get('SQL ID', 'N/A')} · Plan {plan.get('Plan Hash', 'N/A')}"
                                st.markdown(
                                    f"**{header}**  \nSchema: {plan.get('Schema', 'N/A')} · Module: {plan.get('Module', 'N/A')} · "
                                    f"Execs: {plan.get('Executions', 'N/A')} · Last Active: {plan.get('Last Active', 'N/A')}"
                                )
                                st.code(plan.get('SQL Text Full') or plan.get('SQL Text') or 'N/A', language='sql')
                else:
                    st.info("No recent SQL statistics available (live or historical).")

            with tab13:
                st.subheader("Host Metrics Detail")
                if host_metrics:
                    load_avg = host_metrics.get('load_avg', (0, 0, 0))
                    st.write(f"**CPU Cores:** {host_metrics.get('cpu_count', 'N/A')}")
                    st.write(f"**Load Average (1/5/15 min):** {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}")
                    st.write(f"**Process Memory:** {host_metrics.get('process_memory_mb', 0):.1f} MB")
                    st.write(f"**Swap Usage:** {host_metrics.get('swap_percent', 0):.1f}%")
                else:
                    st.info("Host metrics not available on this platform.")

            with tab14:
                st.subheader("🚦 All Sessions Traffic (Active & Inactive)")
                st.markdown("**Real-time view of all database sessions with traffic metrics**")
                
                all_sessions = monitor.get_all_sessions_traffic()
                if all_sessions:
                    df_all_traffic = pd.DataFrame(all_sessions)
                    
                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total = len(df_all_traffic)
                        st.metric("Total Sessions", total)
                    with col2:
                        active = len(df_all_traffic[df_all_traffic['Status'] == 'ACTIVE'])
                        st.metric("Active Sessions", active, help="Sessions currently executing")
                    with col3:
                        inactive = len(df_all_traffic[df_all_traffic['Status'] == 'INACTIVE'])
                        st.metric("Inactive Sessions", inactive, help="Sessions idle/waiting")
                    with col4:
                        blocked = len(df_all_traffic[df_all_traffic['Blocking Session'].notna()])
                        st.metric("Blocked Sessions", blocked, help="Sessions being blocked")
                    
                    # Filter by status
                    status_filter = st.multiselect(
                        "Filter by Status",
                        options=['ACTIVE', 'INACTIVE'],
                        default=['ACTIVE', 'INACTIVE'],
                        help="Select session statuses to display"
                    )
                    
                    if status_filter:
                        df_filtered = df_all_traffic[df_all_traffic['Status'].isin(status_filter)]
                    else:
                        df_filtered = df_all_traffic
                    
                    # Show data table
                    st.dataframe(df_filtered, hide_index=True, width='stretch', height=600)
                    
                    # Traffic visualization - Top users by logical reads
                    st.markdown("### 📈 Traffic Distribution")
                    top_n = st.slider("Show top N sessions", 5, 20, 10)
                    
                    df_top_traffic = df_filtered.nlargest(top_n, 'Logical Reads (MB)')
                    
                    fig_traffic = px.bar(
                        df_top_traffic,
                        x='SID',
                        y=['Logical Reads (MB)', 'Physical Reads (MB)'],
                        title=f"Top {top_n} Sessions by I/O Traffic",
                        labels={'value': 'MB', 'variable': 'Read Type'},
                        barmode='group'
                    )
                    st.plotly_chart(fig_traffic, width='stretch', key="traffic_sessions_top_io")
                    
                    # CPU distribution
                    df_top_cpu = df_filtered.nlargest(top_n, 'CPU (seconds)')
                    fig_cpu = px.bar(
                        df_top_cpu,
                        x='SID',
                        y='CPU (seconds)',
                        color='Status',
                        title=f"Top {top_n} Sessions by CPU Usage",
                        labels={'CPU (seconds)': 'CPU Time (seconds)'}
                    )
                    st.plotly_chart(fig_cpu, width='stretch', key="traffic_sessions_top_cpu")
                    
                    # Status breakdown pie chart
                    status_counts = df_all_traffic['Status'].value_counts()
                    fig_pie = px.pie(
                        values=status_counts.values,
                        names=status_counts.index,
                        title="Session Status Distribution"
                    )
                    st.plotly_chart(fig_pie, width='stretch', key="traffic_sessions_status")
                    
                else:
                    st.info("No session traffic data available")
            
            with tab15:
                st.subheader("📊 Traffic Grouped by User & Program")
                st.markdown("**Identify which users and applications are causing high database traffic**")
                
                grouped_sessions = monitor.get_sessions_grouped_by_traffic()
                if grouped_sessions:
                    df_grouped = pd.DataFrame(grouped_sessions)
                    
                    # Summary
                    st.markdown("### Overview")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        unique_users = df_grouped['Username'].nunique()
                        st.metric("Unique Users", unique_users)
                    with col2:
                        unique_programs = df_grouped['Program'].nunique()
                        st.metric("Unique Programs", unique_programs)
                    with col3:
                        total_sessions = df_grouped['Total Sessions'].sum()
                        st.metric("Total Sessions", int(total_sessions))
                    
                    # Data table with all groups
                    st.markdown("### 📋 All Groups")
                    st.dataframe(df_grouped, hide_index=True, width='stretch', height=400)
                    
                    # Top traffic generators
                    st.markdown("### 🔥 Top Traffic Generators")
                    
                    top_count = st.slider("Show top N groups", 5, 20, 10, key="traffic_top_n_live")
                    
                    # By logical reads
                    st.markdown("#### By Logical Reads (MB)")
                    df_top_logical = df_grouped.nlargest(top_count, 'Total Logical Reads (MB)')
                    
                    # Create combined label for better visualization
                    df_top_logical['Group'] = df_top_logical['Username'] + '\n' + df_top_logical['Program']
                    
                    fig_logical = px.bar(
                        df_top_logical,
                        x='Group',
                        y='Total Logical Reads (MB)',
                        color='Total Sessions',
                        title=f"Top {top_count} User/Program Groups by Logical Reads",
                        labels={'Total Logical Reads (MB)': 'Logical Reads (MB)', 'Group': 'User / Program'},
                        color_continuous_scale='Reds'
                    )
                    fig_logical.update_xaxes(tickangle=-45)
                    st.plotly_chart(fig_logical, width='stretch', key="traffic_grouped_logical_live")
                    
                    # By CPU usage
                    st.markdown("#### By CPU Usage (seconds)")
                    df_top_cpu = df_grouped.nlargest(top_count, 'Total CPU (seconds)')
                    df_top_cpu['Group'] = df_top_cpu['Username'] + '\n' + df_top_cpu['Program']
                    
                    fig_cpu_grouped = px.bar(
                        df_top_cpu,
                        x='Group',
                        y='Total CPU (seconds)',
                        color='Active Sessions',
                        title=f"Top {top_count} User/Program Groups by CPU",
                        labels={'Total CPU (seconds)': 'CPU Time (seconds)', 'Group': 'User / Program'},
                        color_continuous_scale='Oranges'
                    )
                    fig_cpu_grouped.update_xaxes(tickangle=-45)
                    st.plotly_chart(fig_cpu_grouped, width='stretch', key="traffic_grouped_cpu_live")
                    
                    # Session count breakdown
                    st.markdown("#### By Session Count")
                    df_top_sessions = df_grouped.nlargest(top_count, 'Total Sessions')
                    df_top_sessions['Group'] = df_top_sessions['Username'] + '\n' + df_top_sessions['Program']
                    
                    fig_sessions = px.bar(
                        df_top_sessions,
                        x='Group',
                        y=['Active Sessions', 'Inactive Sessions'],
                        title=f"Top {top_count} User/Program Groups by Session Count",
                        labels={'value': 'Sessions', 'variable': 'Status', 'Group': 'User / Program'},
                        barmode='stack'
                    )
                    fig_sessions.update_xaxes(tickangle=-45)
                    st.plotly_chart(fig_sessions, width='stretch', key="traffic_grouped_sessions_live")
                    
                    # Detailed breakdown by user
                    st.markdown("### 👤 Breakdown by User")
                    user_summary = df_grouped.groupby('Username').agg({
                        'Total Sessions': 'sum',
                        'Active Sessions': 'sum',
                        'Inactive Sessions': 'sum',
                        'Total Logical Reads (MB)': 'sum',
                        'Total CPU (seconds)': 'sum'
                    }).reset_index().sort_values('Total Logical Reads (MB)', ascending=False)
                    
                    st.dataframe(user_summary, hide_index=True, width='stretch')
                    
                    # Pie chart for user distribution
                    fig_user_pie = px.pie(
                        user_summary.head(10),
                        values='Total Sessions',
                        names='Username',
                        title='Top 10 Users by Session Count'
                    )
                    st.plotly_chart(fig_user_pie, width='stretch', key="traffic_grouped_user_pie_live")
                    
                    # Detailed breakdown by program
                    st.markdown("### 💻 Breakdown by Program")
                    program_summary = df_grouped.groupby('Program').agg({
                        'Total Sessions': 'sum',
                        'Active Sessions': 'sum',
                        'Inactive Sessions': 'sum',
                        'Total Logical Reads (MB)': 'sum',
                        'Total CPU (seconds)': 'sum'
                    }).reset_index().sort_values('Total Logical Reads (MB)', ascending=False)
                    
                    st.dataframe(program_summary, hide_index=True, width='stretch')
                    
                    # Pie chart for program distribution
                    fig_program_pie = px.pie(
                        program_summary.head(10),
                        values='Total Sessions',
                        names='Program',
                        title='Top 10 Programs by Session Count'
                    )
                    st.plotly_chart(fig_program_pie, width='stretch', key="traffic_grouped_program_pie_live")
                    
                else:
                    st.info("No grouped session data available")
            
            with tab16:
                st.subheader("SQLite History Explorer")
                if monitor.history_store:
                    history_limit = st.slider(
                        "History depth (rows)",
                        min_value=50,
                        max_value=500,
                        value=200,
                        step=50,
                        help="Number of rows to pull from the SQLite history store."
                    )
                    metrics_history = monitor.history_store.fetch_recent_metrics(history_limit)
                    if metrics_history:
                        df_sqlite_metrics = pd.DataFrame(metrics_history)
                        df_sqlite_metrics['timestamp'] = pd.to_datetime(df_sqlite_metrics['timestamp'], format='ISO8601')
                        st.markdown("**Recent Metrics (SQLite)**")
                        st.dataframe(df_sqlite_metrics.sort_values('timestamp', ascending=False), hide_index=True, width='stretch')

                        fig_sqlite = px.line(
                            df_sqlite_metrics.sort_values('timestamp'),
                            x='timestamp',
                            y=['total_sessions', 'active_sessions', 'blocked_sessions'],
                            title="Session Metrics (SQLite History)",
                            labels={'value': 'Count', 'timestamp': 'Time'}
                        )
                        st.plotly_chart(fig_sqlite, width='stretch')
                    else:
                        st.info("No metrics have been persisted to SQLite yet.")

                    st.markdown("---")
                    st.markdown("**Tablespace History (SQLite)**")
                    available_tablespaces = monitor.history_store.list_tablespaces()
                    ts_filter = st.selectbox(
                        "Tablespace filter",
                        options=["(All Tablespaces)"] + available_tablespaces if available_tablespaces else ["(All Tablespaces)"],
                        index=0
                    )
                    ts_history = monitor.history_store.fetch_tablespace_history(
                        None if ts_filter == "(All Tablespaces)" else ts_filter,
                        limit=history_limit
                    )
                    if ts_history:
                        df_ts_history = pd.DataFrame(ts_history)
                        df_ts_history['timestamp'] = pd.to_datetime(df_ts_history['timestamp'], format='ISO8601')
                        st.dataframe(df_ts_history.sort_values(['tablespace', 'timestamp'], ascending=False),
                                     hide_index=True,
                                     width='stretch')
                        fig_ts = px.line(
                            df_ts_history.sort_values('timestamp'),
                            x='timestamp',
                            y='pct_used',
                            color='tablespace',
                            title="Tablespace Utilization History",
                            labels={'pct_used': '% Used', 'timestamp': 'Time'}
                        )
                        st.plotly_chart(fig_ts, width='stretch')
                    else:
                        st.info("No tablespace history stored yet.")

                    st.markdown("---")
                    st.markdown("**I/O History (SQLite)**")
                    io_history = monitor.history_store.fetch_io_history(history_limit)
                    if io_history:
                        df_io_history = pd.DataFrame(io_history)
                        df_io_history['timestamp'] = pd.to_datetime(df_io_history['timestamp'], format='ISO8601')
                        st.dataframe(df_io_history.sort_values('timestamp', ascending=False),
                                     hide_index=True,
                                     width='stretch')
                        fig_io_hist = px.line(
                            df_io_history.sort_values('timestamp'),
                            x='timestamp',
                            y=['Read MB', 'Write MB'],
                            color='Username',
                            title="Historical Storage I/O",
                            labels={'value': 'MB', 'timestamp': 'Time'}
                        )
                        st.plotly_chart(fig_io_hist, width='stretch')
                    else:
                        st.info("No I/O history stored yet.")

                    st.markdown("---")
                    st.markdown("**Wait Events History (SQLite)**")
                    wait_history = monitor.history_store.fetch_wait_history(history_limit)
                    if wait_history:
                        df_wait_hist = pd.DataFrame(wait_history)
                        df_wait_hist['timestamp'] = pd.to_datetime(df_wait_hist['timestamp'], format='ISO8601')
                        st.dataframe(df_wait_hist.sort_values('timestamp', ascending=False),
                                     hide_index=True,
                                     width='stretch')
                        fig_wait_hist = px.bar(
                            df_wait_hist.sort_values('timestamp'),
                            x='timestamp',
                            y='Total Wait (s)',
                            color='Wait Class',
                            title="Historical Wait Events",
                            labels={'timestamp': 'Time'}
                        )
                        st.plotly_chart(fig_wait_hist, width='stretch')
                    else:
                        st.info("No wait event history stored yet.")

                    st.markdown("---")
                    st.markdown("**Temp Usage History (SQLite)**")
                    temp_history = monitor.history_store.fetch_temp_history(history_limit)
                    if temp_history:
                        df_temp_hist = pd.DataFrame(temp_history)
                        df_temp_hist['timestamp'] = pd.to_datetime(df_temp_hist['timestamp'], format='ISO8601')
                        st.dataframe(df_temp_hist.sort_values('timestamp', ascending=False),
                                     hide_index=True,
                                     width='stretch')
                    else:
                        st.info("No temp usage history stored yet.")

                    st.markdown("---")
                    st.markdown("**Undo Metrics History (SQLite)**")
                    undo_history = monitor.history_store.fetch_undo_history(history_limit)
                    if undo_history:
                        df_undo_hist = pd.DataFrame(undo_history)
                        df_undo_hist['timestamp'] = pd.to_datetime(df_undo_hist['timestamp'], format='ISO8601')
                        st.dataframe(df_undo_hist.sort_values('timestamp', ascending=False),
                                     hide_index=True,
                                     width='stretch')
                    else:
                        st.info("No undo history stored yet.")

                    st.markdown("---")
                    st.markdown("**Redo Metrics History (SQLite)**")
                    redo_history = monitor.history_store.fetch_redo_history(history_limit)
                    if redo_history:
                        df_redo_hist = pd.DataFrame(redo_history)
                        df_redo_hist['timestamp'] = pd.to_datetime(df_redo_hist['timestamp'], format='ISO8601')
                        st.dataframe(df_redo_hist.sort_values('timestamp', ascending=False),
                                     hide_index=True,
                                     width='stretch')
                    else:
                        st.info("No redo history stored yet.")

                    st.markdown("---")
                    st.markdown("**Plan History (SQLite)**")
                    plan_history = monitor.history_store.fetch_plan_history(history_limit)
                    if plan_history:
                        df_plan_hist = pd.DataFrame(plan_history)
                        df_plan_hist['timestamp'] = pd.to_datetime(df_plan_hist['timestamp'], format='ISO8601')
                        st.dataframe(df_plan_hist.sort_values('timestamp', ascending=False),
                                     hide_index=True,
                                     width='stretch')
                    else:
                        st.info("No plan history stored yet.")
                    
                    st.markdown("---")
                    st.markdown("**All Sessions Traffic History (SQLite)**")
                    all_traffic_history = monitor.history_store.fetch_all_sessions_traffic_history(history_limit)
                    if all_traffic_history:
                        df_traffic_hist = pd.DataFrame(all_traffic_history)
                        df_traffic_hist['timestamp'] = pd.to_datetime(df_traffic_hist['timestamp'], format='ISO8601')
                        st.dataframe(df_traffic_hist.sort_values('timestamp', ascending=False),
                                     hide_index=True,
                                     width='stretch',
                                     height=400)
                        
                        # Visualization
                        fig_traffic_hist = px.line(
                            df_traffic_hist.sort_values('timestamp'),
                            x='timestamp',
                            y=['Logical Reads (MB)', 'Physical Reads (MB)'],
                            color='Username',
                            title="Historical Session Traffic by User",
                            labels={'value': 'MB', 'timestamp': 'Time'}
                        )
                        st.plotly_chart(fig_traffic_hist, width='stretch')
                    else:
                        st.info("No traffic history stored yet.")

                    st.markdown("---")
                    st.markdown("**Grouped Traffic History (SQLite)**")
                    grouped_traffic_history = monitor.history_store.fetch_grouped_traffic_history(history_limit)
                    if grouped_traffic_history:
                        df_grouped_hist = pd.DataFrame(grouped_traffic_history)
                        df_grouped_hist['timestamp'] = pd.to_datetime(df_grouped_hist['timestamp'], format='ISO8601')
                        st.dataframe(df_grouped_hist.sort_values('timestamp', ascending=False),
                                     hide_index=True,
                                     width='stretch',
                                     height=400)
                        
                        # Visualization - Top programs by traffic over time
                        fig_grouped_hist = px.bar(
                            df_grouped_hist.sort_values(['timestamp', 'Total Logical Reads (MB)'], ascending=[True, False]).head(50),
                            x='timestamp',
                            y='Total Logical Reads (MB)',
                            color='Program',
                            title="Top Programs by Traffic Over Time",
                            labels={'Total Logical Reads (MB)': 'Logical Reads (MB)', 'timestamp': 'Time'}
                        )
                        st.plotly_chart(fig_grouped_hist, width='stretch')
                    else:
                        st.info("No grouped traffic history stored yet.")
                else:
                    st.info("SQLite history store is not initialized.")
            
            # Display alerts if any
            if alerts:
                for alert in alerts:
                    st.warning(f"⚠️ {alert}")
            
            # Show log files info
            with st.expander("📁 Log Files (for AI Analysis)"):
                st.info("""
                All monitoring data is logged to multiple files in the `logs/` directory:
                - **metrics.jsonl** - Structured metrics in JSON Lines format
                - **metrics.csv** - Metrics in CSV format for easy analysis
                - **alerts.jsonl** - All alerts and warnings in JSON format
                - **sessions.jsonl** - Detailed session information
                - **tablespaces.jsonl** - Tablespace usage snapshots for AI analysis
                - **tablespace_usage.csv** - Historical tablespace utilization
                - **io_sessions.jsonl** - Storage I/O heavy sessions
                - **io_sessions.csv** - CSV export of I/O sessions
                - **wait_events.jsonl** - Wait event samples
                - **temp_usage.jsonl** - Temp/undo utilization snapshots
                - **redo_metrics.jsonl** - Redo/log writer metrics
                - **plan_churn.jsonl** - Recent SQL plan statistics
                - **traffic_sessions.jsonl** - Real-time session traffic snapshots
                - **traffic_groups.jsonl** - Aggregated traffic by user/program
                - **monitor_history.db** - SQLite database with metrics/tablespace history
                - **app.log** - Application events and errors
                - **app_events.jsonl** - Structured application events
                
                These files are optimized for AI agent analysis and can be easily parsed.
                """)
                if LOG_DIR.exists():
                    log_files = list(LOG_DIR.glob('*'))
                    if log_files:
                        st.write("**Available log files:**")
                        for log_file in sorted(log_files):
                            try:
                                size = log_file.stat().st_size
                            except FileNotFoundError:
                                continue
                            st.write(f"- `{log_file.name}` ({size:,} bytes)")
            
            # Auto-refresh if monitoring
                    st.markdown("### 📋 All Groups")
                    st.dataframe(df_grouped, hide_index=True, width='stretch', height=400)
                    
                    # Top traffic generators
                    st.markdown("### 🔥 Top Traffic Generators")
                    
                    top_count = st.slider("Show top N groups", 5, 20, 10, key="traffic_top_n_history")
                    
                    # By logical reads
                    st.markdown("#### By Logical Reads (MB)")
                    df_top_logical = df_grouped.nlargest(top_count, 'Total Logical Reads (MB)')
                    
                    # Create combined label for better visualization
                    df_top_logical['Group'] = df_top_logical['Username'] + '\n' + df_top_logical['Program']
                    
                    fig_logical = px.bar(
                        df_top_logical,
                        x='Group',
                        y='Total Logical Reads (MB)',
                        color='Total Sessions',
                        title=f"Top {top_count} User/Program Groups by Logical Reads",
                        labels={'Total Logical Reads (MB)': 'Logical Reads (MB)', 'Group': 'User / Program'},
                        color_continuous_scale='Reds'
                    )
                    fig_logical.update_xaxes(tickangle=-45)
                    st.plotly_chart(fig_logical, width='stretch', key="traffic_grouped_logical_history")
                    
                    # By CPU usage
                    st.markdown("#### By CPU Usage (seconds)")
                    df_top_cpu = df_grouped.nlargest(top_count, 'Total CPU (seconds)')
                    df_top_cpu['Group'] = df_top_cpu['Username'] + '\n' + df_top_cpu['Program']
                    
                    fig_cpu_grouped = px.bar(
                        df_top_cpu,
                        x='Group',
                        y='Total CPU (seconds)',
                        color='Active Sessions',
                        title=f"Top {top_count} User/Program Groups by CPU",
                        labels={'Total CPU (seconds)': 'CPU Time (seconds)', 'Group': 'User / Program'},
                        color_continuous_scale='Oranges'
                    )
                    fig_cpu_grouped.update_xaxes(tickangle=-45)
                    st.plotly_chart(fig_cpu_grouped, width='stretch', key="traffic_grouped_cpu_history")
                    
                    # Session count breakdown
                    st.markdown("#### By Session Count")
                    df_top_sessions = df_grouped.nlargest(top_count, 'Total Sessions')
                    df_top_sessions['Group'] = df_top_sessions['Username'] + '\n' + df_top_sessions['Program']
                    
                    fig_sessions = px.bar(
                        df_top_sessions,
                        x='Group',
                        y=['Active Sessions', 'Inactive Sessions'],
                        title=f"Top {top_count} User/Program Groups by Session Count",
                        labels={'value': 'Sessions', 'variable': 'Status', 'Group': 'User / Program'},
                        barmode='stack'
                    )
                    fig_sessions.update_xaxes(tickangle=-45)
                    st.plotly_chart(fig_sessions, width='stretch', key="traffic_grouped_sessions_history")
                    
                    # Detailed breakdown by user
                    st.markdown("### 👤 Breakdown by User")
                    user_summary = df_grouped.groupby('Username').agg({
                        'Total Sessions': 'sum',
                        'Active Sessions': 'sum',
                        'Inactive Sessions': 'sum',
                        'Total Logical Reads (MB)': 'sum',
                        'Total CPU (seconds)': 'sum'
                    }).reset_index().sort_values('Total Logical Reads (MB)', ascending=False)
                    
                    st.dataframe(user_summary, hide_index=True, width='stretch')
                    
                    # Pie chart for user distribution
                    fig_user_pie = px.pie(
                        user_summary.head(10),
                        values='Total Sessions',
                        names='Username',
                        title='Top 10 Users by Session Count'
                    )
                    st.plotly_chart(fig_user_pie, width='stretch', key="traffic_grouped_user_pie_history")
                    
                    # Detailed breakdown by program
                    st.markdown("### 💻 Breakdown by Program")
                    program_summary = df_grouped.groupby('Program').agg({
                        'Total Sessions': 'sum',
                        'Active Sessions': 'sum',
                        'Inactive Sessions': 'sum',
                        'Total Logical Reads (MB)': 'sum',
                        'Total CPU (seconds)': 'sum'
                    }).reset_index().sort_values('Total Logical Reads (MB)', ascending=False)
                    
                    st.dataframe(program_summary, hide_index=True, width='stretch')
                    
                    # Pie chart for program distribution
                    fig_program_pie = px.pie(
                        program_summary.head(10),
                        values='Total Sessions',
                        names='Program',
                        title='Top 10 Programs by Session Count'
                    )
                    st.plotly_chart(fig_program_pie, width='stretch', key="traffic_grouped_program_pie_history")
                    
                else:
                    st.info("No grouped session data available")
            
            # Display alerts if any
            if alerts:
                for alert in alerts:
                    st.warning(f"⚠️ {alert}")
            
            # Show log files info
            with st.expander("📁 Log Files (for AI Analysis)"):
                st.info("""
                All monitoring data is logged to multiple files in the `logs/` directory:
                - **metrics.jsonl** - Structured metrics in JSON Lines format
                - **metrics.csv** - Metrics in CSV format for easy analysis
                - **alerts.jsonl** - All alerts and warnings in JSON format
                - **sessions.jsonl** - Detailed session information
                - **tablespaces.jsonl** - Tablespace usage snapshots for AI analysis
                - **tablespace_usage.csv** - Historical tablespace utilization
                - **io_sessions.jsonl** - Storage I/O heavy sessions
                - **io_sessions.csv** - CSV export of I/O sessions
                - **wait_events.jsonl** - Wait event samples
                - **temp_usage.jsonl** - Temp/undo utilization snapshots
                - **redo_metrics.jsonl** - Redo/log writer metrics
                - **plan_churn.jsonl** - Recent SQL plan statistics
                - **monitor_history.db** - SQLite database with metrics/tablespace history
                - **app.log** - Application events and errors
                - **app_events.jsonl** - Structured application events
                
                These files are optimized for AI agent analysis and can be easily parsed.
                """)
                if LOG_DIR.exists():
                    log_files = list(LOG_DIR.glob('*'))
                    if log_files:
                        st.write("**Available log files:**")
                        for log_file in sorted(log_files):
                            try:
                                size = log_file.stat().st_size
                            except FileNotFoundError:
                                continue
                            st.write(f"- `{log_file.name}` ({size:,} bytes)")
            
            # Auto-refresh if monitoring
            if st.session_state.monitoring:
                interval = st.session_state.get('refresh_interval', st.session_state.config['monitoring']['interval_seconds'])
                time.sleep(interval)
                st.rerun()
        else:
            st.error("Failed to retrieve session data")


if __name__ == '__main__':
    main()
# --- END: main ---

