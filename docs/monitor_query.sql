-- Quick monitoring query to run every minute
-- This query provides a snapshot of current session status

SET PAGESIZE 0
SET FEEDBACK OFF
SET VERIFY OFF
SET HEADING ON

SELECT 
    TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS') AS check_time,
    COUNT(*) AS total_sessions,
    COUNT(CASE WHEN s.status = 'ACTIVE' THEN 1 END) AS active_sessions,
    COUNT(CASE WHEN s.status = 'INACTIVE' THEN 1 END) AS inactive_sessions,
    COUNT(CASE WHEN s.blocking_session IS NOT NULL THEN 1 END) AS blocked_sessions,
    ROUND(SUM(stat_logical.value) / 1024 / 1024, 2) AS total_logical_reads_mb,
    ROUND(SUM(stat_physical.value) / 1024 / 1024, 2) AS total_physical_reads_mb,
    ROUND(SUM(stat_cpu.value) / 100, 2) AS total_cpu_seconds
FROM v$session s
LEFT JOIN v$sesstat stat_logical ON s.sid = stat_logical.sid 
    AND stat_logical.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'session logical reads')
LEFT JOIN v$sesstat stat_physical ON s.sid = stat_physical.sid 
    AND stat_physical.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'physical reads')
LEFT JOIN v$sesstat stat_cpu ON s.sid = stat_cpu.sid 
    AND stat_cpu.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'CPU used by this session')
WHERE s.username IS NOT NULL;

-- Show top 5 resource-consuming sessions
SELECT 
    'TOP_SESSIONS:' AS info,
    sid,
    serial#,
    username,
    program,
    status,
    ROUND(logical_reads_mb, 2) AS logical_reads_mb,
    ROUND(cpu_seconds, 2) AS cpu_seconds,
    event
FROM (
    SELECT 
        s.sid,
        s.serial#,
        s.username,
        s.program,
        s.status,
        stat_logical.value / 1024 / 1024 AS logical_reads_mb,
        stat_cpu.value / 100 AS cpu_seconds,
        s.event
    FROM v$session s
    LEFT JOIN v$sesstat stat_logical ON s.sid = stat_logical.sid 
        AND stat_logical.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'session logical reads')
    LEFT JOIN v$sesstat stat_cpu ON s.sid = stat_cpu.sid 
        AND stat_cpu.statistic# = (SELECT statistic# FROM v$statname WHERE name = 'CPU used by this session')
    WHERE s.username IS NOT NULL
    ORDER BY stat_logical.value DESC
    FETCH FIRST 5 ROWS ONLY
);

EXIT;

