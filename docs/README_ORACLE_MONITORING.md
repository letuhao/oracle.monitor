# Oracle Session Monitoring Guide

## Overview
This guide helps you monitor Oracle database session usage over a 30-minute period to identify performance issues and potential problems.

## Quick Start

### Option 1: Manual Monitoring (Recommended for immediate diagnosis)

1. **Connect to Oracle:**
   ```bash
   sqlplus username/password@tns_name
   ```

2. **Run the comprehensive monitoring script:**
   ```sql
   @oracle_session_monitor.sql
   ```

3. **For quick checks, run this query every minute:**
   ```sql
   SELECT 
       TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS') AS check_time,
       COUNT(*) AS total_sessions,
       COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) AS active_sessions,
       COUNT(CASE WHEN blocking_session IS NOT NULL THEN 1 END) AS blocked_sessions,
       ROUND(SUM(logical_reads) / 1024 / 1024, 2) AS total_logical_reads_mb,
       ROUND(SUM(cpu_time) / 1000000, 2) AS total_cpu_seconds
   FROM v$session
   WHERE username IS NOT NULL;
   ```

### Option 2: Automated Monitoring Script

**Windows:**
```bash
monitor_oracle_sessions.bat username password tns_name
```

**Linux/Unix:**
```bash
# Create a similar shell script or use:
for i in {1..30}; do
    echo "[$(date)] Iteration $i"
    sqlplus -s username/password@tns_name @monitor_query.sql >> session_log.txt
    sleep 60
done
```

## Key Queries Explained

### 1. Current Active Sessions Overview
Shows overall session statistics including total, active, inactive, and blocked sessions.

### 2. Top Sessions by Resource Usage
Identifies sessions consuming the most CPU, memory, and I/O resources. **Critical for finding problem sessions.**

### 3. Blocking Sessions
Shows which sessions are blocking others. **High priority to resolve blocking issues.**

### 4. Long Running Queries
Identifies queries running longer than 5 minutes. These may need optimization or termination.

### 5. Session Wait Events
Shows what sessions are waiting for (I/O, locks, etc.). Helps identify bottlenecks.

### 6. Resource Limits Check
Checks if you're approaching Oracle's session/process limits. **Critical if database might break.**

## Emergency Actions

### If Database is Overloaded:

1. **Identify problem sessions:**
   ```sql
   SELECT sid, serial#, username, program, status, sql_id, 
          ROUND(cpu_time/1000000, 2) AS cpu_sec,
          ROUND(logical_reads/1024/1024, 2) AS reads_mb
   FROM v$session
   WHERE username IS NOT NULL
   ORDER BY cpu_time DESC
   FETCH FIRST 10 ROWS ONLY;
   ```

2. **Check for blocking:**
   ```sql
   SELECT blocking.sid AS blocker, blocked.sid AS blocked, 
          blocked.seconds_in_wait AS wait_sec
   FROM v$session blocking
   JOIN v$session blocked ON blocking.sid = blocked.blocking_session;
   ```

3. **Kill problematic sessions (use with caution):**
   ```sql
   -- First, try to kill gracefully
   ALTER SYSTEM KILL SESSION 'sid,serial#' IMMEDIATE;
   
   -- If that doesn't work, use:
   ALTER SYSTEM DISCONNECT SESSION 'sid,serial#' IMMEDIATE;
   ```

4. **Check resource limits:**
   ```sql
   SELECT resource_name, current_utilization, max_utilization, limit_value
   FROM v$resource_limit
   WHERE resource_name IN ('sessions', 'processes');
   ```

## Monitoring Checklist

During the 30-minute monitoring period, check:

- [ ] **Total sessions** - Is it approaching the limit?
- [ ] **Active sessions** - Are there too many active sessions?
- [ ] **Blocked sessions** - Are sessions blocking each other?
- [ ] **CPU usage** - Which sessions are consuming the most CPU?
- [ ] **I/O usage** - Are there excessive disk reads/writes?
- [ ] **Long-running queries** - Are queries taking too long?
- [ ] **Wait events** - What are sessions waiting for?

## Interpreting Results

### Warning Signs:
- **High blocked_sessions count** → Deadlocks or locking issues
- **Sessions approaching limit_value** → Database may reject new connections
- **High cpu_time or logical_reads** → Resource-intensive queries
- **Long seconds_in_wait** → Sessions waiting for resources
- **Many ACTIVE sessions** → High concurrent load

### Action Items:
1. If sessions approaching limit → Increase PROCESSES/SESSIONS parameters
2. If blocking detected → Identify and resolve blocking sessions
3. If high resource usage → Optimize or kill problematic queries
4. If wait events → Investigate specific wait events (I/O, locks, etc.)

## Files Included

- `oracle_session_monitor.sql` - Comprehensive monitoring queries
- `monitor_query.sql` - Quick snapshot query for repeated execution
- `monitor_oracle_sessions.bat` - Windows batch script for automated monitoring
- `README_ORACLE_MONITORING.md` - This guide

## Notes

- Run queries as a user with SELECT privileges on `V$SESSION`, `V$SQL`, and related views
- For historical data, you need AWR (Automatic Workload Repository) enabled
- Some queries may require DBA privileges
- Always review before killing sessions - killing active transactions can cause data issues

## Additional Resources

- Oracle V$SESSION view documentation
- Oracle Performance Tuning Guide
- Oracle Database Administrator's Guide

