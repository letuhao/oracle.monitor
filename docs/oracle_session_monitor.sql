-- Oracle Session Monitoring Queries for 30-minute period
-- Use these queries to monitor session usage and identify potential issues

-- ============================================
-- 1. Current Active Sessions Overview
-- ============================================
-- Shows current active sessions with key metrics
SELECT 
    COUNT(*) AS total_sessions,
    COUNT(CASE WHEN s.status = 'ACTIVE' THEN 1 END) AS active_sessions,
    COUNT(CASE WHEN s.status = 'INACTIVE' THEN 1 END) AS inactive_sessions,
    COUNT(CASE WHEN s.blocking_session IS NOT NULL THEN 1 END) AS blocked_sessions,
    ROUND(SUM(stat_logical.value) / 1024 / 1024, 2) AS total_logical_reads_mb,
    ROUND(SUM(stat_physical.value) / 1024 / 1024, 2) AS total_physical_reads_mb,
    ROUND(SUM(stat_cpu.value) / 100, 2) AS total_cpu_time_seconds
FROM v$session s
LEFT JOIN v$sesstat stat_logical ON s.sid = stat_logical.sid 
    AND stat_logical.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'session logical reads')
LEFT JOIN v$sesstat stat_physical ON s.sid = stat_physical.sid 
    AND stat_physical.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'physical reads')
LEFT JOIN v$sesstat stat_cpu ON s.sid = stat_cpu.sid 
    AND stat_cpu.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'CPU used by this session')
WHERE s.username IS NOT NULL;

-- ============================================
-- 2. Top Sessions by Resource Usage
-- ============================================
-- Identifies sessions consuming the most resources
SELECT 
    s.sid,
    s.serial#,
    s.username,
    s.program,
    s.machine,
    s.status,
    s.logon_time,
    ROUND(stat_logical.value / 1024 / 1024, 2) AS logical_reads_mb,
    ROUND(stat_physical.value / 1024 / 1024, 2) AS physical_reads_mb,
    ROUND(stat_cpu.value / 100, 2) AS cpu_time_seconds,
    s.blocking_session,
    s.event,
    s.seconds_in_wait,
    s.sql_id,
    s.sql_child_number
FROM v$session s
LEFT JOIN v$sesstat stat_logical ON s.sid = stat_logical.sid 
    AND stat_logical.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'session logical reads')
LEFT JOIN v$sesstat stat_physical ON s.sid = stat_physical.sid 
    AND stat_physical.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'physical reads')
LEFT JOIN v$sesstat stat_cpu ON s.sid = stat_cpu.sid 
    AND stat_cpu.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'CPU used by this session')
WHERE s.username IS NOT NULL
ORDER BY stat_logical.value DESC
FETCH FIRST 20 ROWS ONLY;

-- ============================================
-- 3. Session Count by Status and Type
-- ============================================
-- Breakdown of sessions by status and type
SELECT 
    status,
    type,
    COUNT(*) AS session_count
FROM v$session
WHERE username IS NOT NULL
GROUP BY status, type
ORDER BY session_count DESC;

-- ============================================
-- 4. Long Running Queries (Running > 5 minutes)
-- ============================================
-- Identifies queries that have been running for a while
SELECT 
    s.sid,
    s.serial#,
    s.username,
    s.program,
    s.status,
    s.logon_time,
    ROUND((SYSDATE - s.logon_time) * 24 * 60, 2) AS minutes_connected,
    s.sql_id,
    s.sql_child_number,
    q.sql_text,
    s.event,
    s.seconds_in_wait,
    ROUND(stat_cpu.value / 100, 2) AS cpu_time_seconds
FROM v$session s
LEFT JOIN v$sql q ON s.sql_id = q.sql_id AND s.sql_child_number = q.child_number
LEFT JOIN v$sesstat stat_cpu ON s.sid = stat_cpu.sid 
    AND stat_cpu.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'CPU used by this session')
WHERE s.username IS NOT NULL
    AND s.status = 'ACTIVE'
    AND (SYSDATE - s.logon_time) * 24 * 60 > 5  -- More than 5 minutes
ORDER BY (SYSDATE - s.logon_time) DESC;

-- ============================================
-- 5. Blocking Sessions
-- ============================================
-- Shows sessions that are blocking other sessions
SELECT 
    blocking.sid AS blocking_sid,
    blocking.serial# AS blocking_serial#,
    blocking.username AS blocking_user,
    blocking.program AS blocking_program,
    blocking.sql_id AS blocking_sql_id,
    blocked.sid AS blocked_sid,
    blocked.serial# AS blocked_serial#,
    blocked.username AS blocked_user,
    blocked.program AS blocked_program,
    blocked.sql_id AS blocked_sql_id,
    blocked.event AS wait_event,
    blocked.seconds_in_wait AS wait_seconds
FROM v$session blocking
JOIN v$session blocked ON blocking.sid = blocked.blocking_session
WHERE blocking.username IS NOT NULL
ORDER BY blocked.seconds_in_wait DESC;

-- ============================================
-- 6. Session Wait Events
-- ============================================
-- Shows what sessions are waiting for
SELECT 
    s.sid,
    s.serial#,
    s.username,
    s.program,
    s.event,
    s.seconds_in_wait,
    s.wait_class,
    s.state,
    s.sql_id
FROM v$session s
WHERE s.username IS NOT NULL
    AND s.wait_class != 'Idle'
    AND s.seconds_in_wait > 0
ORDER BY s.seconds_in_wait DESC;

-- ============================================
-- 7. Session Count by Program/Application
-- ============================================
-- Shows which applications are using the most sessions
SELECT 
    program,
    machine,
    COUNT(*) AS session_count,
    COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) AS active_count
FROM v$session
WHERE username IS NOT NULL
GROUP BY program, machine
ORDER BY session_count DESC;

-- ============================================
-- 8. Session History (if AWR is available)
-- ============================================
-- Historical session data from last 30 minutes (requires AWR)
SELECT 
    TO_CHAR(sample_time, 'YYYY-MM-DD HH24:MI:SS') AS sample_time,
    COUNT(*) AS active_sessions,
    ROUND(AVG(cpu_time / 1000000), 2) AS avg_cpu_seconds,
    ROUND(SUM(logical_reads) / 1024 / 1024, 2) AS total_logical_reads_mb
FROM dba_hist_active_sess_history
WHERE sample_time >= SYSDATE - (30/1440)  -- Last 30 minutes
GROUP BY sample_time
ORDER BY sample_time DESC;

-- ============================================
-- 9. Real-time Monitoring Query (Run every minute)
-- ============================================
-- Use this query repeatedly to track changes over time
SELECT 
    TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS') AS check_time,
    COUNT(*) AS total_sessions,
    COUNT(CASE WHEN s.status = 'ACTIVE' THEN 1 END) AS active_sessions,
    COUNT(CASE WHEN s.blocking_session IS NOT NULL THEN 1 END) AS blocked_sessions,
    ROUND(SUM(stat_logical.value) / 1024 / 1024, 2) AS total_logical_reads_mb,
    ROUND(SUM(stat_cpu.value) / 100, 2) AS total_cpu_seconds
FROM v$session s
LEFT JOIN v$sesstat stat_logical ON s.sid = stat_logical.sid 
    AND stat_logical.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'session logical reads')
LEFT JOIN v$sesstat stat_cpu ON s.sid = stat_cpu.sid 
    AND stat_cpu.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'CPU used by this session')
WHERE s.username IS NOT NULL;

-- ============================================
-- 10. Emergency: Kill Long-Running Problem Sessions
-- ============================================
-- WARNING: Use with caution! Review before executing
-- Uncomment and modify SID and SERIAL# before running
/*
ALTER SYSTEM KILL SESSION 'SID,SERIAL#' IMMEDIATE;
-- Example: ALTER SYSTEM KILL SESSION '123,456' IMMEDIATE;
*/

-- ============================================
-- 11. Session Resource Limits Check
-- ============================================
-- Check if you're approaching session limits
SELECT 
    resource_name,
    current_utilization,
    max_utilization,
    limit_value,
    ROUND((current_utilization / limit_value) * 100, 2) AS usage_percent
FROM v$resource_limit
WHERE resource_name IN ('sessions', 'processes', 'transactions')
ORDER BY usage_percent DESC;

-- ============================================
-- 12. SQL Statements Consuming Most Resources
-- ============================================
-- Identify SQL statements that are resource-intensive
SELECT 
    s.sql_id,
    s.sql_text,
    COUNT(*) AS execution_count,
    ROUND(SUM(s.cpu_time) / 1000000, 2) AS total_cpu_seconds,
    ROUND(SUM(s.elapsed_time) / 1000000, 2) AS total_elapsed_seconds,
    ROUND(SUM(s.buffer_gets) / 1024 / 1024, 2) AS total_buffer_gets_mb,
    ROUND(SUM(s.disk_reads) / 1024 / 1024, 2) AS total_disk_reads_mb
FROM v$sql s
JOIN v$session sess ON s.sql_id = sess.sql_id
WHERE sess.username IS NOT NULL
GROUP BY s.sql_id, s.sql_text
ORDER BY total_cpu_seconds DESC
FETCH FIRST 10 ROWS ONLY;

