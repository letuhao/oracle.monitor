# Oracle Database Session Monitor

Read-only monitoring tool for Oracle 19+ databases. Monitors session usage, resource consumption, and potential issues without modifying any data.

## Features

- ✅ **Read-only monitoring** - No INSERT/UPDATE/DELETE queries
- ✅ **Real-time session tracking** - Monitor active sessions, blocked sessions, resource usage
- ✅ **Alert system** - Configurable thresholds for warnings
- ✅ **Historical logging** - CSV export for analysis
- ✅ **Top sessions identification** - Find resource-intensive sessions
- ✅ **Blocking detection** - Identify sessions blocking others
- ✅ **Streamlit dashboard** - Interactive charts and drill-downs

### Metrics & Insights

The monitor collects and visualizes the following signals every interval:

- **Session load**: total sessions, active/inactive split, blocked session count
- **Resource pressure**: CPU seconds, logical vs physical reads (MB), IO wait breakdown
- **Blocking/locking**: blocker SID/user, wait events, chains depth
- **Top SQL / sessions**: highest CPU/time consumers with username/SID and SQL hash
- **Trend lines**: rolling averages and sparkline history for each major metric
- **Alerts**: thresholds for max sessions, active sessions, blocked sessions, CPU% with WARN/CRITICAL badges in the GUI and JSONL logs

### GUI Metric Inventory

The Streamlit dashboard (`oracle_monitor_gui.py`) exposes **18 metric families** end‑to‑end:

1. **Session overview** – `get_session_overview()` returns total/active/inactive/blocked sessions plus logical & physical reads and CPU seconds for the summary cards.
2. **Session status mix** – `get_session_by_status()` feeds the pie chart of ACTIVE/INACTIVE/OTHER counts.
3. **Historical persistence** – the embedded `HistoryStore` captures every sample (sessions, IO, waits, tablespaces, undo, redo, plans) for the SQLite explorer tab.
4. **Host metrics** – `get_host_metrics()` tracks host CPU%, memory%, process CPU/memory, swap, load average, and logical core count.
5. **Resource limits & alerts** – `get_resource_limits()` and the configured thresholds compare live usage to limits for processes, sessions, PGA, SGA, and tablespace pct.
6. **Top sessions** – `get_top_sessions()` surfaces per‑session logical reads, CPU seconds, SQL text, plan hash, and wait event.
7. **High CPU sessions** – `get_top_cpu_sessions()` highlights CPU‑heavy work, including SQL/module/action metadata.
8. **Session resource usage** – `get_session_resource_usage()` captures CPU(s), PGA MB/max MB, OS thread id, machine, and SQL info.
9. **Grouped swarm analysis** – `group_sessions()` aggregates counts, total CPU, and total PGA by user, program, module, or SQL ID.
10. **Blocking topology** – `get_blocking_sessions()` plus `get_blocking_chains()` report blockers, blocked SIDs, wait events, wait seconds, and chain depth.
11. **Tablespace utilization** – `get_tablespace_usage()` measures used/allocated/max MB, free MB, pct used, autoextend headroom, and file counts.
12. **Storage I/O hot spots** – `get_io_sessions()` records per‑session read/write/temp MB and related SQL text.
13. **Wait event profile** – `get_wait_events()` aggregates top non‑idle waits with sessions, total wait seconds, and avg wait ms.
14. **Temp usage** – `get_temp_usage()` shows tablespace, segment type, used MB, and owning session for temp consumers.
15. **Undo health** – `get_undo_metrics()` reports undo blocks, transactions, max query length, ORA‑01555 / no‑space counts, and tuned retention.
16. **Redo / log writer** – `get_redo_metrics()` exposes redo size, writes, write time, and log file sync waits/time.
17. **Plan churn** – `get_plan_churn()` lists SQL IDs, plan hashes, executions, elapsed seconds, buffer gets, disk reads, rows processed, and last active time.
18. **Storage history explorer** – the SQLite tab rehydrates sessions, tablespaces, IO, waits, temp, undo, redo, and plan data for retrospectives.

## Technology Stack

- **Language**: Python 3.7+
- **Database Library**: `oracledb` (Oracle's official Python library)
- **GUI Framework**: `streamlit` (Modern web-based dashboard)
- **Visualization**: `plotly` (Interactive charts)
- **Data Processing**: `pandas` (Data manipulation)
- **Why Python?**: 
  - Easy to use and maintain
  - Great for monitoring scripts
  - Cross-platform support
  - Rich ecosystem
  - Excellent GUI libraries (Streamlit)

## Quick Start (GUI)

1. **Clone and install**
   ```bash
   git clone https://github.com/YourGitHubUsername/oracle.monitor.git
   cd oracle.monitor
   python -m venv .venv && .venv\\Scripts\\activate  # PowerShell (Windows)
   source .venv/bin/activate                          # bash/zsh (macOS/Linux)
   pip install -r requirements.txt
   ```
   
   > ⚠️ **Note**: Replace `YourGitHubUsername` with your actual GitHub username before publishing
2. **Create a local config**
   - Copy `config.example.json` to `config.local.json`
   - Fill in your Oracle connection details (read-only user recommended)
   - Export the path so the app can find it:
     ```powershell
     $env:ORACLE_MONITOR_CONFIG="config.local.json"
     ```
     ```bash
     export ORACLE_MONITOR_CONFIG=config.local.json
     ```
3. **Run the GUI dashboard**
   ```bash
   streamlit run oracle_monitor_gui.py
   ```
   or use the launchers: `run_gui.bat` (Windows) / `run_gui.sh` (macOS/Linux).
4. **Verify data remains local**
   - Logs land in `logs/` (ignored by Git)
   - `config.local.json` stays untracked (rename if needed, or add to `.git/info/exclude`)

For CLI usage or advanced setup, keep reading.

## Installation

### 1. Install Python

Ensure Python 3.7+ is installed:
```bash
python --version
```

### 2. Install Dependencies

```bash
cd dwh-monitor
pip install -r requirements.txt
```

Or install directly:
```bash
pip install oracledb
```

### 3. Configure Database Connection

Create a private copy based on `config.example.json` (e.g., `config.local.json`) and point the app to it with the `ORACLE_MONITOR_CONFIG` environment variable. Avoid storing real credentials in `config.json` to keep them out of Git.

```json
{
  "database": {
    "host": "your_oracle_host",
    "port": 1521,
    "service_name": "ORCL",
    "username": "your_username",
    "password": "your_password"
  },
  "monitoring": {
    "interval_seconds": 60,
    "duration_minutes": 30,
    "log_file": "monitor_log.txt",
    "csv_output": "session_history.csv",
    "alert_thresholds": {
      "max_sessions": 500,
      "max_active_sessions": 200,
      "max_blocked_sessions": 10,
      "max_cpu_percent": 80
    }
  }
}
```

## Usage

### 🖥️ GUI Version (Recommended)

The GUI version provides a modern web-based dashboard with real-time charts and visualizations.

**Windows:**
```bash
run_gui.bat
```

**Linux/Mac:**
```bash
chmod +x run_gui.sh
./run_gui.sh
```

**Manual:**
```bash
streamlit run oracle_monitor_gui.py
```

The GUI will:
- Open automatically in your default web browser
- Show real-time metrics with charts and graphs
- Display top sessions and blocking information
- Provide historical trend analysis
- Allow CSV export of monitoring data

**Features:**
- 📊 Interactive dashboards with live charts
- 📈 Historical trend visualization
- 🔝 Top sessions table with sorting
- 🔒 Blocking sessions detection
- 💾 CSV export functionality
- ⚙️ Easy configuration in sidebar

### 📟 Command-Line Version

**Basic Usage:**
```bash
python oracle_monitor.py
```

**Custom Configuration File:**
```bash
python oracle_monitor.py -c my_config.json
```

**Run in Background (Linux/Mac):**
```bash
nohup python oracle_monitor.py > monitor_output.log 2>&1 &
```

**Run in Background (Windows):**
```powershell
Start-Process python -ArgumentList "oracle_monitor.py" -WindowStyle Hidden
```

## Output Files

### 1. Console/Log Output

Real-time monitoring information printed to console and `oracle_monitor.log`:

```
2024-01-15 10:30:00 - INFO - === Monitoring cycle at 2024-01-15 10:30:00 ===
2024-01-15 10:30:00 - INFO - Total Sessions: 150
2024-01-15 10:30:00 - INFO - Active Sessions: 45
2024-01-15 10:30:00 - INFO - Blocked Sessions: 2
2024-01-15 10:30:00 - WARNING - CRITICAL: Blocked sessions (2) exceeds threshold (10)
```

### 2. CSV Historical Data

`session_history.csv` contains timestamped data for analysis:

```csv
timestamp,total_sessions,active_sessions,inactive_sessions,blocked_sessions,logical_reads_mb,physical_reads_mb,cpu_seconds,top_session_sid,top_session_cpu,alert_status
2024-01-15 10:30:00,150,45,105,2,1250.50,350.25,1250.75,123,45.2,OK
```

## Monitoring Queries (All Read-Only)

The tool uses only SELECT queries from Oracle views:

- `v$session` - Session information
- `v$sesstat` - Session statistics
- `v$statname` - Statistic names
- `v$sql` - SQL statement information (for top sessions)

**No data modification**: All queries are SELECT statements only.

## Configuration Options

### Database Connection

- `host`: Oracle database hostname/IP
- `port`: Oracle listener port (default: 1521)
- `service_name`: Oracle service name
- `username`: Database username (needs SELECT on V$ views)
- `password`: Database password

### Monitoring Settings

- `interval_seconds`: How often to check (default: 60 seconds)
- `duration_minutes`: Total monitoring duration (default: 30 minutes)
- `log_file`: Log file path
- `csv_output`: CSV output file path

### Alert Thresholds

- `max_sessions`: Maximum total sessions before warning
- `max_active_sessions`: Maximum active sessions before warning
- `max_blocked_sessions`: Maximum blocked sessions before critical alert
- `max_cpu_percent`: Maximum CPU usage percentage (future use)

## Required Database Permissions

The database user needs SELECT privileges on:

```sql
GRANT SELECT ON v_$session TO your_username;
GRANT SELECT ON v_$sesstat TO your_username;
GRANT SELECT ON v_$statname TO your_username;
GRANT SELECT ON v_$sql TO your_username;
```

Or grant through role:
```sql
GRANT SELECT_CATALOG_ROLE TO your_username;
```

## Troubleshooting

### Connection Issues

1. **Check Oracle connection string**:
   ```bash
   sqlplus username/password@host:port/service_name
   ```

2. **Verify network connectivity**:
   ```bash
   telnet oracle_host 1521
   ```

3. **Check Oracle listener**:
   ```bash
   lsnrctl status
   ```

### Permission Issues

If you get "table or view does not exist" errors:

1. Connect as DBA and grant permissions:
   ```sql
   GRANT SELECT_CATALOG_ROLE TO your_username;
   ```

2. Or grant specific views:
   ```sql
   GRANT SELECT ON v_$session TO your_username;
   GRANT SELECT ON v_$sesstat TO your_username;
   GRANT SELECT ON v_$statname TO your_username;
   ```

### Library Issues

If `oracledb` installation fails:

1. **Install Oracle Instant Client** (required for oracledb):
   - Download from Oracle website
   - Extract and set environment variables
   - Or use `pip install oracledb[thin]` for thin mode (no client needed)

2. **Alternative**: Use `cx_Oracle` (older library):
   ```bash
   pip install cx_Oracle
   ```
   Then modify imports in `oracle_monitor.py`

## Example Output

```
2024-01-15 10:30:00 - INFO - Successfully connected to Oracle database
2024-01-15 10:30:00 - INFO - Starting monitoring for 30 minutes
2024-01-15 10:30:00 - INFO - Monitoring interval: 60 seconds
2024-01-15 10:30:00 - INFO - Total iterations: 30
2024-01-15 10:30:00 - INFO - ============================================================
2024-01-15 10:30:00 - INFO - === Monitoring cycle at 2024-01-15 10:30:00 ===
2024-01-15 10:30:00 - INFO - Total Sessions: 150
2024-01-15 10:30:00 - INFO - Active Sessions: 45
2024-01-15 10:30:00 - INFO - Inactive Sessions: 105
2024-01-15 10:30:00 - INFO - Blocked Sessions: 2
2024-01-15 10:30:00 - INFO - Logical Reads: 1250.50 MB
2024-01-15 10:30:00 - INFO - Physical Reads: 350.25 MB
2024-01-15 10:30:00 - INFO - CPU Time: 1250.75 seconds
2024-01-15 10:30:00 - INFO - Top 5 Resource-Consuming Sessions:
2024-01-15 10:30:00 - INFO -   1. SID:123 User:APP_USER CPU:45.20s Reads:250.50MB
2024-01-15 10:30:00 - INFO -   2. SID:456 User:APP_USER CPU:32.10s Reads:180.25MB
```

## Logging for AI Agent Analysis

The GUI application automatically logs all monitoring data to multiple files in the `logs/` directory:

- **metrics.jsonl** - Structured metrics in JSON Lines format (one JSON object per line)
- **metrics.csv** - Metrics in CSV format for spreadsheet/statistical analysis
- **alerts.jsonl** - All alerts and warnings in structured JSON format
- **sessions.jsonl** - Detailed session information (top sessions, blocking sessions)
- **app.log** - Human-readable application events and errors
- **app_events.jsonl** - Structured application events in JSON format

All log files are optimized for AI agent analysis and can be easily parsed programmatically. See [LOGGING.md](LOGGING.md) for detailed documentation on log formats and analysis examples.

## Security Notes

- **Never commit passwords** to version control
- Use environment variables or secure vaults for production
- The tool only performs SELECT queries - no data modification
- Consider using read-only database user for monitoring
- **Log files may contain connection information** - Do not commit log files (already in `.gitignore`)

## License

This tool is provided as-is for monitoring purposes.

