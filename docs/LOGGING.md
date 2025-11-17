# Logging Documentation for AI Agent Analysis

The Oracle Monitor GUI application outputs comprehensive logs in multiple formats optimized for AI agent analysis.

## Log File Structure

All log files are stored in the `logs/` directory and are created automatically when the application runs.

### 1. Metrics Logs

#### `metrics.jsonl` (JSON Lines Format)
Each line is a JSON object containing metrics snapshot:
```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "type": "metrics",
  "data": {
    "total_sessions": 150,
    "active_sessions": 45,
    "inactive_sessions": 105,
    "blocked_sessions": 2,
    "logical_reads_mb": 1250.50,
    "physical_reads_mb": 350.25,
    "cpu_seconds": 1250.75
  }
}
```

**Format**: JSON Lines (one JSON object per line)
**Use Case**: Easy parsing for AI agents, time-series analysis
**Frequency**: Every monitoring cycle (default: every 5 seconds when monitoring)

#### `metrics.csv` (CSV Format)
Comma-separated values for spreadsheet/statistical analysis:
```csv
timestamp,total_sessions,active_sessions,inactive_sessions,blocked_sessions,logical_reads_mb,physical_reads_mb,cpu_seconds,alert_count
2024-01-15 10:30:00,150,45,105,2,1250.50,350.25,1250.75,1
```

**Format**: CSV with header row
**Use Case**: Excel, pandas, statistical analysis
**Frequency**: Every monitoring cycle

### 2. Alerts Log

#### `alerts.jsonl` (JSON Lines Format)
All alerts and warnings in structured format:
```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "type": "alert",
  "alert_type": "critical",
  "message": "Blocked sessions (12) exceeds threshold (10)",
  "details": {
    "metric": "blocked_sessions",
    "value": 12,
    "threshold": 10
  }
}
```

**Alert Types**:
- `warning` - Non-critical threshold exceeded
- `critical` - Critical issue detected (e.g., blocking sessions)
- `info` - Informational alerts

**Format**: JSON Lines
**Use Case**: Alert analysis, anomaly detection, pattern recognition
**Frequency**: Only when alerts occur

### 3. Session Details Log

#### `sessions.jsonl` (JSON Lines Format)
Detailed information about sessions:
```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "type": "session",
  "session_type": "top",
  "data": {
    "SID": 123,
    "Serial#": 456,
    "Username": "APP_USER",
    "Program": "myapp.exe",
    "Status": "ACTIVE",
    "Logical Reads (MB)": 250.50,
    "CPU (seconds)": 45.20,
    "Wait Event": "db file sequential read",
    "SQL ID": "abc123def456"
  }
}
```

**Session Types**:
- `top` - Top resource-consuming sessions
- `blocking` - Sessions that are blocking others
- `blocked` - Sessions being blocked

**Format**: JSON Lines
**Use Case**: Session analysis, performance profiling, resource tracking
**Frequency**: Every monitoring cycle (for top sessions), when blocking detected

### 4. Application Events Log

#### `app.log` (Text Format)
Human-readable application log:
```
2024-01-15 10:30:00|INFO|oracle_monitor_app|CONNECT: Connected to localhost:1521/ORCL
2024-01-15 10:30:05|INFO|oracle_monitor_app|MONITOR_START: Monitoring started
2024-01-15 10:30:10|WARNING|oracle_monitor_app|ALERT [critical]: Blocked sessions (12) exceeds threshold (10)
```

**Format**: Pipe-delimited text (`timestamp|level|logger|message`)
**Use Case**: Human review, debugging, audit trail
**Frequency**: On application events

#### `app_events.jsonl` (JSON Lines Format)
Structured application events:
```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "event_type": "connect",
  "message": "Connected to localhost:1521/ORCL",
  "details": {
    "host": "localhost",
    "port": 1521,
    "service_name": "ORCL",
    "username": "monitor_user"
  }
}
```

**Event Types**:
- `connect` - Database connection established
- `disconnect` - Database connection closed
- `monitor_start` - Monitoring started
- `monitor_stop` - Monitoring stopped
- `error` - Error occurred

**Format**: JSON Lines
**Use Case**: Event analysis, workflow tracking, error analysis
**Frequency**: On application events

## AI Agent Analysis Examples

### Example 1: Parse Metrics JSONL
```python
import json

metrics = []
with open('logs/metrics.jsonl', 'r') as f:
    for line in f:
        metrics.append(json.loads(line))

# Analyze trends
total_sessions_trend = [m['data']['total_sessions'] for m in metrics]
```

### Example 2: Analyze Alerts
```python
import json

critical_alerts = []
with open('logs/alerts.jsonl', 'r') as f:
    for line in f:
        alert = json.loads(line)
        if alert['alert_type'] == 'critical':
            critical_alerts.append(alert)
```

### Example 3: Load CSV Metrics
```python
import pandas as pd

df = pd.read_csv('logs/metrics.csv', parse_dates=['timestamp'])
# Analyze trends
df.plot(x='timestamp', y='total_sessions')
```

### Example 4: Find Problem Sessions
```python
import json

problem_sessions = []
with open('logs/sessions.jsonl', 'r') as f:
    for line in f:
        session = json.loads(line)
        if session['data']['CPU (seconds)'] > 100:
            problem_sessions.append(session)
```

## Log File Rotation

Currently, log files grow continuously. For production use, consider:

1. **Manual Rotation**: Stop application, rename/archive logs, restart
2. **Log Rotation Tools**: Use `logrotate` (Linux) or similar tools
3. **Size Limits**: Implement file size limits in future versions

## Best Practices for AI Analysis

1. **Use JSONL format** for structured data analysis
2. **Parse incrementally** - Read line by line for large files
3. **Combine data sources** - Cross-reference alerts with metrics and sessions
4. **Time-series analysis** - Use timestamps for trend analysis
5. **Filter by type** - Use `type` field to filter relevant records

## File Locations

- **Windows**: `dwh-monitor\logs\`
- **Linux/Mac**: `dwh-monitor/logs/`

All log files use UTF-8 encoding and are safe for international characters.

## Security Notes

- Log files may contain database connection information (host, port, service name, username)
- **Do not commit log files** to version control (already in `.gitignore`)
- Consider log file access permissions in production environments
- Rotate/archive logs regularly to prevent disk space issues

