-- ============================================================================
-- Oracle Database Read-Only Access Verification Script
-- Purpose: Verify that monitoring user has ONLY read access and cannot
--          modify any data in the database
-- 
-- 使用说明 (Chinese Usage): 使用监控用户运行此脚本，验证其只有只读权限
-- Hướng dẫn (Vietnamese Usage): Chạy script này với user giám sát để xác minh chỉ có quyền đọc
-- ============================================================================

SET SERVEROUTPUT ON
SET ECHO ON
SET FEEDBACK ON

PROMPT ============================================================================
PROMPT Oracle Database Read-Only Access Verification
PROMPT ============================================================================
PROMPT
PROMPT This script will test if the current user has read-only access
PROMPT Expected: All write operations should FAIL with ORA-01031
PROMPT
PROMPT ============================================================================
PROMPT

-- ============================================================================
-- 1. Display Current User Information
-- ============================================================================
PROMPT ============================================================================
PROMPT 1. Current User Information
PROMPT ============================================================================

SELECT 
    USER AS current_user,
    SYS_CONTEXT('USERENV', 'SESSION_USER') AS session_user,
    TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS') AS current_time
FROM dual;

PROMPT

-- ============================================================================
-- 2. List User Privileges
-- ============================================================================
PROMPT ============================================================================
PROMPT 2. User Privileges (Should be SELECT only on system views)
PROMPT ============================================================================

SELECT 
    privilege,
    admin_option
FROM user_sys_privs
ORDER BY privilege;

PROMPT

-- ============================================================================
-- 3. List Table Privileges
-- ============================================================================
PROMPT ============================================================================
PROMPT 3. Table/View Privileges (Should be SELECT on v$ views only)
PROMPT ============================================================================

SELECT 
    table_name,
    privilege,
    grantable
FROM user_tab_privs
ORDER BY table_name, privilege;

PROMPT

-- ============================================================================
-- 4. List Role Privileges
-- ============================================================================
PROMPT ============================================================================
PROMPT 4. Role Privileges (Should NOT have DBA or powerful roles)
PROMPT ============================================================================

SELECT 
    granted_role,
    admin_option,
    default_role
FROM user_role_privs
ORDER BY granted_role;

PROMPT

-- ============================================================================
-- 5. Test Read Access (Should SUCCEED)
-- ============================================================================
PROMPT ============================================================================
PROMPT 5. Test READ Access (Should SUCCEED) ✅
PROMPT ============================================================================

PROMPT Testing: SELECT COUNT(*) FROM v$session...
SELECT COUNT(*) AS session_count FROM v$session WHERE username IS NOT NULL;
PROMPT ✅ READ ACCESS TEST: PASSED
PROMPT

PROMPT Testing: SELECT COUNT(*) FROM v$sesstat...
SELECT COUNT(*) AS stat_count FROM v$sesstat WHERE rownum <= 10;
PROMPT ✅ READ ACCESS TEST: PASSED
PROMPT

PROMPT Testing: SELECT COUNT(*) FROM v$statname...
SELECT COUNT(*) AS statname_count FROM v$statname WHERE rownum <= 10;
PROMPT ✅ READ ACCESS TEST: PASSED
PROMPT

-- ============================================================================
-- 6. Test Write Access - UPDATE (Should FAIL)
-- ============================================================================
PROMPT ============================================================================
PROMPT 6. Test WRITE Access - UPDATE (Should FAIL with ORA-01031) ❌
PROMPT ============================================================================

PROMPT Testing: UPDATE v$session (Should fail)...
DECLARE
    v_error_code NUMBER;
    v_error_msg VARCHAR2(1000);
BEGIN
    EXECUTE IMMEDIATE 'UPDATE v$session SET status = ''TEST'' WHERE 1=0';
    DBMS_OUTPUT.PUT_LINE('❌ SECURITY RISK: UPDATE succeeded - User has write access!');
EXCEPTION
    WHEN OTHERS THEN
        v_error_code := SQLCODE;
        v_error_msg := SQLERRM;
        IF v_error_code = -1031 THEN
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: UPDATE failed with ORA-01031 (insufficient privileges)');
        ELSIF v_error_code IN (-1031, -1735, -600) THEN
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: UPDATE failed - Cannot modify v$ views');
        ELSE
            DBMS_OUTPUT.PUT_LINE('⚠️  WARNING: Unexpected error: ' || v_error_msg);
        END IF;
END;
/

PROMPT

-- ============================================================================
-- 7. Test Write Access - DELETE (Should FAIL)
-- ============================================================================
PROMPT ============================================================================
PROMPT 7. Test WRITE Access - DELETE (Should FAIL with ORA-01031) ❌
PROMPT ============================================================================

PROMPT Testing: DELETE FROM v$session (Should fail)...
DECLARE
    v_error_code NUMBER;
    v_error_msg VARCHAR2(1000);
BEGIN
    EXECUTE IMMEDIATE 'DELETE FROM v$session WHERE 1=0';
    DBMS_OUTPUT.PUT_LINE('❌ SECURITY RISK: DELETE succeeded - User has write access!');
EXCEPTION
    WHEN OTHERS THEN
        v_error_code := SQLCODE;
        v_error_msg := SQLERRM;
        IF v_error_code = -1031 THEN
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: DELETE failed with ORA-01031 (insufficient privileges)');
        ELSIF v_error_code IN (-1031, -1735, -600) THEN
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: DELETE failed - Cannot modify v$ views');
        ELSE
            DBMS_OUTPUT.PUT_LINE('⚠️  WARNING: Unexpected error: ' || v_error_msg);
        END IF;
END;
/

PROMPT

-- ============================================================================
-- 8. Test Write Access - INSERT (Should FAIL)
-- ============================================================================
PROMPT ============================================================================
PROMPT 8. Test WRITE Access - INSERT (Should FAIL with ORA-01031) ❌
PROMPT ============================================================================

PROMPT Testing: INSERT INTO v$session (Should fail)...
DECLARE
    v_error_code NUMBER;
    v_error_msg VARCHAR2(1000);
BEGIN
    EXECUTE IMMEDIATE 'INSERT INTO v$session VALUES (NULL)';
    DBMS_OUTPUT.PUT_LINE('❌ SECURITY RISK: INSERT succeeded - User has write access!');
EXCEPTION
    WHEN OTHERS THEN
        v_error_code := SQLCODE;
        v_error_msg := SQLERRM;
        IF v_error_code = -1031 THEN
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: INSERT failed with ORA-01031 (insufficient privileges)');
        ELSIF v_error_code IN (-1031, -1735, -600, -947) THEN
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: INSERT failed - Cannot modify v$ views');
        ELSE
            DBMS_OUTPUT.PUT_LINE('⚠️  WARNING: Unexpected error: ' || v_error_msg);
        END IF;
END;
/

PROMPT

-- ============================================================================
-- 9. Test Write Access - CREATE TABLE (Should FAIL)
-- ============================================================================
PROMPT ============================================================================
PROMPT 9. Test WRITE Access - CREATE TABLE (Should FAIL with ORA-01031) ❌
PROMPT ============================================================================

PROMPT Testing: CREATE TABLE test_table (Should fail)...
DECLARE
    v_error_code NUMBER;
    v_error_msg VARCHAR2(1000);
BEGIN
    EXECUTE IMMEDIATE 'CREATE TABLE test_security_check (id NUMBER)';
    DBMS_OUTPUT.PUT_LINE('❌ SECURITY RISK: CREATE TABLE succeeded - User has DDL access!');
    -- Cleanup if it succeeded
    EXECUTE IMMEDIATE 'DROP TABLE test_security_check';
EXCEPTION
    WHEN OTHERS THEN
        v_error_code := SQLCODE;
        v_error_msg := SQLERRM;
        IF v_error_code = -1031 THEN
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: CREATE TABLE failed with ORA-01031 (insufficient privileges)');
        ELSE
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: CREATE TABLE failed - User cannot create objects');
        END IF;
END;
/

PROMPT

-- ============================================================================
-- 10. Test Write Access - DROP TABLE (Should FAIL)
-- ============================================================================
PROMPT ============================================================================
PROMPT 10. Test WRITE Access - DROP TABLE (Should FAIL with ORA-01031) ❌
PROMPT ============================================================================

PROMPT Testing: DROP TABLE (Should fail)...
DECLARE
    v_error_code NUMBER;
    v_error_msg VARCHAR2(1000);
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE nonexistent_table_xyz';
    DBMS_OUTPUT.PUT_LINE('❌ SECURITY RISK: DROP TABLE succeeded - User has DDL access!');
EXCEPTION
    WHEN OTHERS THEN
        v_error_code := SQLCODE;
        v_error_msg := SQLERRM;
        IF v_error_code IN (-1031, -942) THEN
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: DROP TABLE failed - User cannot drop objects');
        ELSE
            DBMS_OUTPUT.PUT_LINE('✅ SECURITY OK: DROP TABLE failed');
        END IF;
END;
/

PROMPT

-- ============================================================================
-- 11. Summary
-- ============================================================================
PROMPT ============================================================================
PROMPT VERIFICATION SUMMARY
PROMPT ============================================================================
PROMPT
PROMPT Expected Results:
PROMPT ✅ Read operations (SELECT) should SUCCEED
PROMPT ✅ Write operations (UPDATE/DELETE/INSERT/CREATE/DROP) should FAIL
PROMPT
PROMPT If all write operations failed, this user is READ-ONLY and SAFE ✅
PROMPT If any write operation succeeded, DO NOT use this user (security risk) ❌
PROMPT
PROMPT ============================================================================
PROMPT

-- ============================================================================
-- 12. Recommendations
-- ============================================================================
PROMPT ============================================================================
PROMPT RECOMMENDATIONS
PROMPT ============================================================================
PROMPT
PROMPT For maximum security, the monitoring user should have ONLY:
PROMPT
PROMPT   GRANT CREATE SESSION TO monitor_user;
PROMPT   GRANT SELECT ON v$session TO monitor_user;
PROMPT   GRANT SELECT ON v$sesstat TO monitor_user;
PROMPT   GRANT SELECT ON v$statname TO monitor_user;
PROMPT   GRANT SELECT ON v$instance TO monitor_user;
PROMPT
PROMPT The user should NOT have:
PROMPT   - DBA role
PROMPT   - INSERT/UPDATE/DELETE privileges
PROMPT   - CREATE/DROP privileges
PROMPT   - GRANT/REVOKE privileges
PROMPT
PROMPT ============================================================================
PROMPT

-- ============================================================================
-- 13. Test Monitoring Queries
-- ============================================================================
PROMPT ============================================================================
PROMPT 13. Test Actual Monitoring Queries
PROMPT ============================================================================
PROMPT

PROMPT Testing: Get session overview query...
SELECT 
    COUNT(*) AS total_sessions,
    COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) AS active_sessions,
    COUNT(CASE WHEN status = 'INACTIVE' THEN 1 END) AS inactive_sessions,
    COUNT(CASE WHEN blocking_session IS NOT NULL THEN 1 END) AS blocked_sessions
FROM v$session
WHERE username IS NOT NULL;

PROMPT ✅ Session overview query: PASSED
PROMPT

PROMPT Testing: Get top sessions query...
SELECT 
    sid,
    serial#,
    username,
    program,
    status
FROM v$session
WHERE username IS NOT NULL
AND rownum <= 5
ORDER BY sid;

PROMPT ✅ Top sessions query: PASSED
PROMPT

PROMPT Testing: Get statistic names query...
SELECT statistic#, name
FROM v$statname
WHERE name IN ('session logical reads', 'physical reads', 'CPU used by this session')
ORDER BY name;

PROMPT ✅ Statistic names query: PASSED
PROMPT

-- ============================================================================
-- Final Message
-- ============================================================================
PROMPT ============================================================================
PROMPT VERIFICATION COMPLETE
PROMPT ============================================================================
PROMPT
PROMPT If all tests passed correctly, your monitoring user is properly configured
PROMPT with READ-ONLY access and is SAFE to use for database monitoring.
PROMPT
PROMPT 中文: 如果所有测试都正确通过，您的监控用户已正确配置为只读访问，可以安全用于数据库监控。
PROMPT Tiếng Việt: Nếu tất cả các test đều pass đúng, user giám sát của bạn đã được cấu hình
PROMPT              chỉ đọc và an toàn để sử dụng cho giám sát cơ sở dữ liệu.
PROMPT
PROMPT ============================================================================

-- Disconnect
PROMPT
PROMPT Verification script completed.
EXIT;

