#!/usr/bin/env python3
"""
Oracle Database Session Monitor
Read-only monitoring tool for Oracle 19+ databases
Monitors session usage, resource consumption, and potential issues
"""

import json
import logging
import csv
import time
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import oracledb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('oracle_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class OracleMonitor:
    """Oracle Database Session Monitor - Read-only monitoring"""
    
    def __init__(self, config_path: str = 'config.json'):
        """Initialize monitor with configuration"""
        self.config = self._load_config(config_path)
        self.connection: Optional[oracledb.Connection] = None
        self.csv_writer = None
        self.csv_file = None
        self._init_csv_output()
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {config_path} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            sys.exit(1)
    
    def _init_csv_output(self):
        """Initialize CSV file for historical data"""
        csv_file_path = self.config['monitoring']['csv_output']
        self.csv_file = open(csv_file_path, 'w', newline='', encoding='utf-8')
        fieldnames = [
            'timestamp', 'total_sessions', 'active_sessions', 'inactive_sessions',
            'blocked_sessions', 'logical_reads_mb', 'physical_reads_mb', 
            'cpu_seconds', 'top_session_sid', 'top_session_cpu', 'alert_status'
        ]
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
        self.csv_writer.writeheader()
        logger.info(f"CSV output initialized: {csv_file_path}")
    
    def connect(self) -> bool:
        """Establish connection to Oracle database"""
        try:
            db_config = self.config['database']
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
            
            logger.info("Successfully connected to Oracle database")
            return True
        except oracledb.Error as e:
            logger.error(f"Failed to connect to Oracle database: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
        if self.csv_file:
            self.csv_file.close()
            logger.info("CSV file closed")
    
    def _get_statistic_id(self, cursor: oracledb.Cursor, stat_name: str) -> Optional[int]:
        """Get statistic ID from v$statname"""
        try:
            cursor.execute(
                "SELECT statistic# FROM v$statname WHERE name = :name",
                name=stat_name
            )
            result = cursor.fetchone()
            return result[0] if result else None
        except oracledb.Error as e:
            logger.error(f"Error getting statistic ID for {stat_name}: {e}")
            return None
    
    def get_session_overview(self) -> Dict:
        """Get current session overview - READ ONLY"""
        if not self.connection:
            return {}
        
        try:
            cursor = self.connection.cursor()
            
            # Get statistic IDs
            stat_logical = self._get_statistic_id(cursor, 'session logical reads')
            stat_physical = self._get_statistic_id(cursor, 'physical reads')
            stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')
            
            if not all([stat_logical, stat_physical, stat_cpu]):
                logger.warning("Could not retrieve all statistic IDs")
                return {}
            
            # Main query - READ ONLY
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
            return {}
            
        except oracledb.Error as e:
            logger.error(f"Error getting session overview: {e}")
            return {}
    
    def get_top_sessions(self, limit: int = 10) -> List[Dict]:
        """Get top resource-consuming sessions - READ ONLY"""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            
            # Get statistic IDs
            stat_logical = self._get_statistic_id(cursor, 'session logical reads')
            stat_cpu = self._get_statistic_id(cursor, 'CPU used by this session')
            
            if not all([stat_logical, stat_cpu]):
                return []
            
            # READ ONLY query
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
                    s.sql_id
                FROM v$session s
                LEFT JOIN v$sesstat stat ON s.sid = stat.sid 
                    AND stat.statistic# IN (:stat_logical, :stat_cpu)
                WHERE s.username IS NOT NULL
                GROUP BY s.sid, s.serial#, s.username, s.program, s.status, s.event, s.sql_id
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
                    'sql_id': row[8] or 'N/A'
                })
            
            cursor.close()
            return sessions
            
        except oracledb.Error as e:
            logger.error(f"Error getting top sessions: {e}")
            return []
    
    def get_blocking_sessions(self) -> List[Dict]:
        """Get blocking sessions information - READ ONLY"""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            
            # READ ONLY query
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
            return blocking_info
            
        except oracledb.Error as e:
            logger.error(f"Error getting blocking sessions: {e}")
            return []
    
    def check_alerts(self, overview: Dict) -> List[str]:
        """Check for alert conditions based on thresholds"""
        alerts = []
        thresholds = self.config['monitoring']['alert_thresholds']
        
        if overview.get('total_sessions', 0) >= thresholds['max_sessions']:
            alerts.append(f"WARNING: Total sessions ({overview['total_sessions']}) exceeds threshold ({thresholds['max_sessions']})")
        
        if overview.get('active_sessions', 0) >= thresholds['max_active_sessions']:
            alerts.append(f"WARNING: Active sessions ({overview['active_sessions']}) exceeds threshold ({thresholds['max_active_sessions']})")
        
        if overview.get('blocked_sessions', 0) >= thresholds['max_blocked_sessions']:
            alerts.append(f"CRITICAL: Blocked sessions ({overview['blocked_sessions']}) exceeds threshold ({thresholds['max_blocked_sessions']})")
        
        return alerts
    
    def monitor_once(self) -> Dict:
        """Perform one monitoring cycle - READ ONLY"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"=== Monitoring cycle at {timestamp} ===")
        
        overview = self.get_session_overview()
        if not overview:
            logger.warning("Failed to get session overview")
            return {}
        
        # Log overview
        logger.info(f"Total Sessions: {overview['total_sessions']}")
        logger.info(f"Active Sessions: {overview['active_sessions']}")
        logger.info(f"Inactive Sessions: {overview['inactive_sessions']}")
        logger.info(f"Blocked Sessions: {overview['blocked_sessions']}")
        logger.info(f"Logical Reads: {overview['logical_reads_mb']:.2f} MB")
        logger.info(f"Physical Reads: {overview['physical_reads_mb']:.2f} MB")
        logger.info(f"CPU Time: {overview['cpu_seconds']:.2f} seconds")
        
        # Check alerts
        alerts = self.check_alerts(overview)
        for alert in alerts:
            logger.warning(alert)
        
        # Get top sessions
        top_sessions = self.get_top_sessions(5)
        if top_sessions:
            logger.info("Top 5 Resource-Consuming Sessions:")
            for i, session in enumerate(top_sessions, 1):
                logger.info(f"  {i}. SID:{session['sid']} User:{session['username']} "
                          f"CPU:{session['cpu_seconds']:.2f}s Reads:{session['logical_reads_mb']:.2f}MB")
        
        # Check blocking sessions
        blocking = self.get_blocking_sessions()
        if blocking:
            logger.warning(f"Found {len(blocking)} blocking session(s):")
            for block in blocking:
                logger.warning(f"  Blocking SID:{block['blocking_sid']} -> Blocked SID:{block['blocked_sid']} "
                             f"Wait:{block['wait_seconds']}s")
        
        # Write to CSV
        top_session_sid = top_sessions[0]['sid'] if top_sessions else None
        top_session_cpu = top_sessions[0]['cpu_seconds'] if top_sessions else 0
        
        csv_row = {
            'timestamp': timestamp,
            'total_sessions': overview['total_sessions'],
            'active_sessions': overview['active_sessions'],
            'inactive_sessions': overview['inactive_sessions'],
            'blocked_sessions': overview['blocked_sessions'],
            'logical_reads_mb': overview['logical_reads_mb'],
            'physical_reads_mb': overview['physical_reads_mb'],
            'cpu_seconds': overview['cpu_seconds'],
            'top_session_sid': top_session_sid,
            'top_session_cpu': top_session_cpu,
            'alert_status': '; '.join(alerts) if alerts else 'OK'
        }
        self.csv_writer.writerow(csv_row)
        self.csv_file.flush()
        
        return overview
    
    def run(self):
        """Run continuous monitoring"""
        if not self.connect():
            logger.error("Failed to establish database connection")
            return
        
        try:
            interval = self.config['monitoring']['interval_seconds']
            duration_minutes = self.config['monitoring']['duration_minutes']
            total_iterations = (duration_minutes * 60) // interval
            
            logger.info(f"Starting monitoring for {duration_minutes} minutes")
            logger.info(f"Monitoring interval: {interval} seconds")
            logger.info(f"Total iterations: {total_iterations}")
            logger.info("=" * 60)
            
            for iteration in range(total_iterations):
                self.monitor_once()
                
                if iteration < total_iterations - 1:
                    logger.info(f"Waiting {interval} seconds until next check...")
                    time.sleep(interval)
            
            logger.info("=" * 60)
            logger.info("Monitoring completed successfully")
            
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error during monitoring: {e}")
        finally:
            self.disconnect()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Oracle Database Session Monitor')
    parser.add_argument('-c', '--config', default='config.json',
                       help='Path to configuration file (default: config.json)')
    
    args = parser.parse_args()
    
    monitor = OracleMonitor(args.config)
    monitor.run()


if __name__ == '__main__':
    main()

