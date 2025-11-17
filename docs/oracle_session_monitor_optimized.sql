-- Oracle 19 Session Monitoring Queries (Optimized Version)
-- Uses CTE to get statistic numbers once for better performance

-- ============================================
-- Quick Session Overview (Most Efficient)
-- ============================================
WITH stat_names AS (
    SELECT 
        (SELECT statistic# FROM v$statname WHERE name = 'session logical reads') AS stat_logical_reads,
        (SELECT statistic# FROM v$statname WHERE name = 'physical reads') AS stat_physical_reads,
        (SELECT statistic# FROM v$statname WHERE name = 'CPU used by this session') AS stat_cpu
    FROM dual
)
SELECT 
    TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS') AS check_time,
    COUNT(*) AS total_sessions,
    COUNT(CASE WHEN s.status = 'ACTIVE' THEN 1 END) AS active_sessions,
    COUNT(CASE WHEN s.status = 'INACTIVE' THEN 1 END) AS inactive_sessions,
    COUNT(CASE WHEN s.blocking_session IS NOT NULL THEN 1 END) AS blocked_sessions,
    ROUND(SUM(CASE WHEN stat.statistic# = sn.stat_logical_reads THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS total_logical_reads_mb,
    ROUND(SUM(CASE WHEN stat.statistic# = sn.stat_physical_reads THEN stat.value ELSE 0 END) / 1024 / 1024, 2) AS total_physical_reads_mb,
    ROUND(SUM(CASE WHEN stat.statistic# = sn.stat_cpu THEN stat.value ELSE 0 END) / 100, 2) AS total_cpu_seconds
FROM v$session s
CROSS JOIN stat_names sn
LEFT JOIN v$sesstat stat ON s.sid = stat.sid 
    AND stat.statistic# IN (sn.stat_logical_reads, sn.stat_physical_reads, sn.stat_cpu)
WHERE s.username IS NOT NULL
GROUP BY sn.stat_logical_reads, sn.stat_physical_reads, sn.stat_cpu;

-- ============================================
-- Top Sessions by Resource Usage (Optimized)
-- ============================================
WITH stat_names AS (
    SELECT 
        (SELECT statistic# FROM v$statname WHERE name = 'session logical reads') AS stat_logical_reads,
        (SELECT statistic# FROM v$statname WHERE name = 'physical reads') AS stat_physical_reads,
        (SELECT statistic# FROM v$statname WHERE name = 'CPU used by this session') AS stat_cpu
    FROM dual
),
session_stats AS (
    SELECT 
        s.sid,
        s.serial#,
        s.username,
        s.program,
        s.machine,
        s.status,
        s.logon_time,
        s.blocking_session,
        s.event,
        s.seconds_in_wait,
        s.sql_id,
        s.sql_child_number,
        MAX(CASE WHEN stat.statistic# = sn.stat_logical_reads THEN stat.value ELSE 0 END) AS logical_reads,
        MAX(CASE WHEN stat.statistic# = sn.stat_physical_reads THEN stat.value ELSE 0 END) AS physical_reads,
        MAX(CASE WHEN stat.statistic# = sn.stat_cpu THEN stat.value ELSE 0 END) AS cpu_time
    FROM v$session s
    CROSS JOIN stat_names sn
    LEFT JOIN v$sesstat stat ON s.sid = stat.sid 
        AND stat.statistic# IN (sn.stat_logical_reads, sn.stat_physical_reads, sn.stat_cpu)
    WHERE s.username IS NOT NULL
    GROUP BY s.sid, s.serial#, s.username, s.program, s.machine, s.status, 
             s.logon_time, s.blocking_session, s.event, s.seconds_in_wait, s.sql_id, s.sql_child_number
)
SELECT 
    sid,
    serial#,
    username,
    program,
    machine,
    status,
    logon_time,
    ROUND(logical_reads / 1024 / 1024, 2) AS logical_reads_mb,
    ROUND(physical_reads / 1024 / 1024, 2) AS physical_reads_mb,
    ROUND(cpu_time / 100, 2) AS cpu_time_seconds,
    blocking_session,
    event,
    seconds_in_wait,
    sql_id,
    sql_child_number
FROM session_stats
ORDER BY logical_reads DESC
FETCH FIRST 20 ROWS ONLY;

-- ============================================
-- Simple Session Count (No Statistics - Fastest)
-- ============================================
SELECT 
    TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS') AS check_time,
    COUNT(*) AS total_sessions,
    COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) AS active_sessions,
    COUNT(CASE WHEN status = 'INACTIVE' THEN 1 END) AS inactive_sessions,
    COUNT(CASE WHEN blocking_session IS NOT NULL THEN 1 END) AS blocked_sessions
FROM v$session
WHERE username IS NOT NULL;

