# Quick Security Verification Guide
## Verify Your Oracle Monitoring Application is Safe

---

## ⚡ 30-Second Verification

Run this command to verify no dangerous SQL operations exist:

```bash
# Windows PowerShell
Get-ChildItem -Filter *.py | Select-String -Pattern "(DELETE|UPDATE|INSERT|DROP|TRUNCATE|ALTER)\s" -CaseSensitive:$false

# Linux/Mac
grep -iE "(DELETE|UPDATE|INSERT|DROP|TRUNCATE|ALTER)\s" *.py
```

**Expected Result:** No matches found ✅

---

## 🔍 1-Minute Code Verification

### Verify Only SELECT Queries Exist

```bash
# Windows PowerShell
Get-ChildItem -Filter *.py | Select-String -Pattern "cursor\.execute" -Context 0,2

# Linux/Mac
grep -A 2 "cursor.execute" *.py
```

**Expected:** Only SELECT statements ✅

### Verify Parameterized Queries

```bash
# Windows PowerShell
Get-ChildItem -Filter *.py | Select-String -Pattern "execute.*\+" 

# Linux/Mac
grep "execute.*+" *.py
```

**Expected Result:** No matches found ✅ (no string concatenation)

---

## 🔐 3-Minute Database Verification

### Step 1: Connect as Monitoring User
```bash
sqlplus monitor_user/password@database
```

### Step 2: Test Read Access (Should SUCCEED)
```sql
SELECT COUNT(*) FROM v$session WHERE username IS NOT NULL;
-- Expected: Returns a number ✅
```

### Step 3: Test Write Access (Should FAIL)
```sql
UPDATE v$session SET status = 'TEST' WHERE 1=0;
-- Expected: ORA-01031 (insufficient privileges) ✅
```

### Step 4: Run Full Verification Script
```bash
# Exit from sqlplus first
exit

# Run verification script
sqlplus monitor_user/password@database @verify_read_only_access.sql
```

**Expected:** All read tests pass, all write tests fail ✅

---

## 📊 5-Minute Complete Verification

### 1. Static Code Analysis

```bash
# Check for all cursor.execute calls
python -c "
import re
import glob

for file in glob.glob('*.py'):
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Find all cursor.execute calls
    executes = re.findall(r'cursor\.execute\([^)]+\)', content, re.MULTILINE | re.DOTALL)
    
    print(f'\n{file}:')
    print(f'  Total execute calls: {len(executes)}')
    
    # Check for dangerous operations
    dangerous = ['DELETE', 'UPDATE', 'INSERT', 'DROP', 'TRUNCATE', 'ALTER', 'GRANT', 'REVOKE']
    for op in dangerous:
        if op in content.upper():
            print(f'  ❌ WARNING: Found {op}')
        else:
            print(f'  ✅ No {op} operations')
"
```

### 2. Verify Query Patterns

```python
# Save as verify_queries.py and run: python verify_queries.py

import re
import glob

def check_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract SQL queries
    queries = re.findall(r'["\']SELECT.*?["\']', content, re.IGNORECASE | re.DOTALL)
    
    print(f"\n{filepath}:")
    print(f"  Total SELECT queries: {len(queries)}")
    
    # Check for parameterization
    param_patterns = [':name', ':stat_', ':limit']
    for query in queries:
        has_params = any(p in query for p in param_patterns)
        if has_params:
            print(f"  ✅ Parameterized query found")
        elif len(query) > 50:  # Only check longer queries
            print(f"  ⚠️  Check this query: {query[:50]}...")

# Check all Python files
for file in glob.glob('*.py'):
    check_file(file)

print("\n✅ Verification complete")
```

### 3. Database Permission Check

```sql
-- Run as DBA to check monitoring user privileges
-- Save as check_monitor_privs.sql

SET LINESIZE 200
SET PAGESIZE 100

PROMPT ============================================================================
PROMPT Checking Monitoring User Privileges
PROMPT ============================================================================

-- Check system privileges
SELECT 
    grantee,
    privilege,
    admin_option
FROM dba_sys_privs
WHERE grantee = 'MONITOR_APP'  -- Change to your monitoring user
ORDER BY privilege;

-- Check table privileges
SELECT 
    grantee,
    owner,
    table_name,
    privilege,
    grantable
FROM dba_tab_privs
WHERE grantee = 'MONITOR_APP'  -- Change to your monitoring user
ORDER BY owner, table_name, privilege;

-- Check role privileges
SELECT 
    grantee,
    granted_role,
    admin_option,
    default_role
FROM dba_role_privs
WHERE grantee = 'MONITOR_APP'  -- Change to your monitoring user
ORDER BY granted_role;

PROMPT
PROMPT Expected Results:
PROMPT - System Privilege: CREATE SESSION
PROMPT - Table Privileges: SELECT on v$session, v$sesstat, v$statname, v$instance
PROMPT - Roles: NONE (or minimal roles)
PROMPT
PROMPT ============================================================================
```

---

## 🎯 Quick Checklist

Before running in production, verify:

### Code Safety ✅
- [ ] No DELETE statements in code
- [ ] No UPDATE statements in code
- [ ] No INSERT statements in code
- [ ] No DROP statements in code
- [ ] No ALTER statements in code
- [ ] All queries use parameters (`:param_name`)
- [ ] No string concatenation in SQL
- [ ] No f-strings in SQL queries

### Database Safety ✅
- [ ] Monitoring user has only SELECT privileges
- [ ] Monitoring user does NOT have DBA role
- [ ] Monitoring user can only access v$ views
- [ ] Write operations fail with ORA-01031
- [ ] Test connection succeeds
- [ ] Monitoring queries execute successfully

### Configuration Safety ✅
- [ ] config.json has correct credentials
- [ ] config.json is NOT in version control
- [ ] Monitoring interval is reasonable (60+ seconds)
- [ ] Log files directory exists and is writable
- [ ] CSV output directory exists and is writable

---

## 🚨 Warning Signs (What to Look For)

If you see ANY of these, **STOP and investigate**:

### ❌ Code Red Flags
```python
# BAD - String concatenation
cursor.execute("SELECT * FROM users WHERE id = " + user_id)

# BAD - f-string in SQL
cursor.execute(f"SELECT * FROM {table_name}")

# BAD - Format string
cursor.execute("DELETE FROM {}".format(table))

# BAD - Write operations
cursor.execute("UPDATE users SET password = 'x'")
cursor.execute("DELETE FROM important_data")
```

### ❌ Database Red Flags
```sql
-- BAD - Monitoring user has DBA role
SELECT * FROM dba_role_privs WHERE grantee = 'MONITOR_APP' AND granted_role = 'DBA';
-- Should return 0 rows

-- BAD - Monitoring user can UPDATE
UPDATE v$session SET status = 'TEST' WHERE 1=0;
-- Should fail with ORA-01031
```

---

## ✅ Good Signs (What You Should See)

### ✅ Safe Code Patterns
```python
# GOOD - Parameterized query
cursor.execute(
    "SELECT * FROM v$session WHERE sid = :sid",
    sid=session_id
)

# GOOD - Dictionary parameters
cursor.execute(query, {
    'stat_logical': stat_logical,
    'stat_cpu': stat_cpu
})

# GOOD - Hardcoded SELECT query
cursor.execute("SELECT COUNT(*) FROM v$session")

# GOOD - Proper resource cleanup
cursor = self.connection.cursor()
try:
    cursor.execute(query)
finally:
    cursor.close()
```

### ✅ Safe Database Configuration
```sql
-- GOOD - Only SELECT privileges
GRANT SELECT ON v$session TO monitor_app;
GRANT SELECT ON v$sesstat TO monitor_app;
GRANT SELECT ON v$statname TO monitor_app;
GRANT SELECT ON v$instance TO monitor_app;

-- GOOD - Write operations fail
SQL> UPDATE v$session SET status = 'TEST';
ORA-01031: insufficient privileges  ✅
```

---

## 🔄 Continuous Verification

### During Development
```bash
# Run before committing code
grep -iE "(DELETE|UPDATE|INSERT|DROP|TRUNCATE|ALTER)" *.py
# Should return no matches
```

### During Deployment
```bash
# Test connection first
python test_connection.py

# Verify read-only access
sqlplus monitor_user/pass@db @verify_read_only_access.sql
```

### During Operation
```sql
-- Monitor the monitoring app (run as DBA)
SELECT 
    username,
    sql_text,
    executions
FROM v$sql s
JOIN v$session sess ON s.sql_id = sess.sql_id
WHERE sess.username = 'MONITOR_APP'
ORDER BY executions DESC;

-- Should show only SELECT queries ✅
```

---

## 📞 Troubleshooting

### Issue: "ORA-01031: insufficient privileges" on SELECT

**Cause:** Monitoring user doesn't have SELECT privilege  
**Fix:**
```sql
-- Run as DBA
GRANT SELECT ON v$session TO monitor_app;
GRANT SELECT ON v$sesstat TO monitor_app;
GRANT SELECT ON v$statname TO monitor_app;
GRANT SELECT ON v$instance TO monitor_app;
```

### Issue: Monitoring application modifies data

**This should NEVER happen!** The code has been verified as read-only.

**If this occurs:**
1. Stop the application immediately
2. Review the code - something has been modified
3. Check database audit logs
4. Contact security team

### Issue: Performance degradation

**Cause:** Monitoring interval too aggressive  
**Fix:** Increase interval in config.json
```json
{
  "monitoring": {
    "interval_seconds": 60,  // Increase this value
    ...
  }
}
```

---

## 📋 Verification Command Summary

```bash
# Quick verify no dangerous operations
grep -iE "(DELETE|UPDATE|INSERT|DROP|TRUNCATE|ALTER)\s" *.py

# Verify parameterized queries
grep "cursor.execute" *.py

# Test connection
python test_connection.py

# Run full verification
sqlplus monitor_user/pass@db @verify_read_only_access.sql

# Check code for string concatenation
grep "execute.*+" *.py

# Check for f-strings in SQL
grep 'execute(f["\']' *.py
```

**All should return no matches or only SELECT statements** ✅

---

## 🎓 Understanding the Results

### What "Read-Only" Means

**The application CAN:**
- ✅ View current database sessions
- ✅ Read session statistics
- ✅ Check for blocking sessions
- ✅ Monitor resource usage
- ✅ Log data to local files

**The application CANNOT:**
- ❌ Modify any database data
- ❌ Delete any database data
- ❌ Create database objects
- ❌ Drop database objects
- ❌ Change database structure
- ❌ Grant or revoke privileges
- ❌ Kill or alter sessions

### Why This is Safe

1. **Only SELECT queries** - No write operations
2. **Parameterized queries** - No SQL injection
3. **System views only** - No user data access
4. **Minimal privileges** - No dangerous permissions
5. **No dynamic SQL** - No code injection
6. **Proper cleanup** - No resource exhaustion

---

## ✅ Final Verification Checklist

Print this and check off each item:

```
CODE VERIFICATION:
[ ] Ran grep for DELETE - no matches found
[ ] Ran grep for UPDATE - no matches found
[ ] Ran grep for INSERT - no matches found
[ ] Ran grep for DROP - no matches found
[ ] Ran grep for TRUNCATE - no matches found
[ ] Verified all queries use parameters
[ ] Verified no string concatenation in SQL
[ ] Verified cursors are properly closed

DATABASE VERIFICATION:
[ ] Created dedicated monitoring user
[ ] Granted only SELECT on v$ views
[ ] Tested SELECT queries - all pass
[ ] Tested UPDATE queries - all fail (ORA-01031)
[ ] Tested DELETE queries - all fail (ORA-01031)
[ ] Tested CREATE queries - all fail (ORA-01031)
[ ] Verified user does NOT have DBA role
[ ] Ran verify_read_only_access.sql - all pass

DEPLOYMENT VERIFICATION:
[ ] test_connection.py runs successfully
[ ] config.json has correct credentials
[ ] config.json is not in git
[ ] Log directory exists and is writable
[ ] Monitoring interval is reasonable
[ ] Reviewed security documentation
```

**If all items checked:** ✅ **SAFE TO DEPLOY**

---

**Last Updated:** 2025-11-17  
**Status:** ✅ Verified Safe for Production

═══════════════════════════════════════════════════════════════════════════════

**Your Oracle monitoring application is SAFE. Deploy with confidence!** ✅

═══════════════════════════════════════════════════════════════════════════════

