# Modular Metrics Architecture

## 🎯 Overview

The Oracle Monitor has been refactored into a **modular, plugin-based architecture** where each metric is self-contained and independently manageable.

### Benefits

✅ **Easy to add new metrics** - Just create a new file, no GUI changes needed  
✅ **No merge conflicts** - Multiple developers can work on different metrics  
✅ **Self-contained** - Each metric handles its own data collection, logging, and storage  
✅ **Auto-discovery** - New metrics are automatically registered  
✅ **Testable** - Each metric can be tested independently  
✅ **Flexible** - Enable/disable metrics without code changes  

---

## 📁 Project Structure

```
oracle.monitor/
├── metrics/                      # Metric modules package
│   ├── __init__.py              # Package initialization
│   ├── base_metric.py           # Base class for all metrics
│   ├── registry.py              # Metric registry and auto-discovery
│   ├── session_overview.py     # Session metrics
│   ├── top_sessions.py          # Top resource consumers
│   ├── blocking_sessions.py    # Blocking detection
│   ├── tablespace_usage.py     # Storage metrics
│   ├── wait_events.py           # Wait event metrics
│   ├── temp_usage.py            # Temp tablespace usage
│   ├── undo_metrics.py          # Undo metrics
│   ├── redo_metrics.py          # Redo metrics
│   ├── plan_churn.py            # SQL plan changes
│   ├── io_sessions.py           # I/O statistics
│   ├── host_metrics.py          # Host system metrics
│   └── resource_limits.py       # Resource limits
├── oracle_monitor_modular.py    # Example GUI using metrics
├── oracle_monitor_gui.py        # Original GUI (to be refactored)
└── logs/                        # Auto-generated log files
    ├── sessionoverviewmetric.jsonl
    ├── topsessionsmetric.jsonl
    ├── blockingsessionsmetric.jsonl
    └── monitor_history.db
```

---

## 🚀 Quick Start

### Using the Modular System

```python
from metrics import get_registry
from pathlib import Path

# Get the registry (auto-discovers all metrics)
registry = get_registry(log_dir=Path("logs"))

# Connect to database
connection = oracledb.connect(...)

# Initialize storage for all metrics
db_path = Path("logs/monitor_history.db")
for metric in registry.get_all_metrics():
    metric.init_storage(db_path)

# Collect data from all enabled metrics
sample_id = datetime.now().isoformat()
results = registry.collect_all(connection)

# Log all metrics to JSONL files
registry.log_all(results, sample_id)

# Store all metrics in SQLite
registry.store_all(db_path, results, sample_id)
```

### Running the Example GUI

```bash
# Run the new modular GUI example
streamlit run oracle_monitor_modular.py
```

---

## 📝 How to Add a New Metric

Adding a new metric takes **3 simple steps**:

### Step 1: Create a new metric file

Create `metrics/my_new_metric.py`:

```python
"""
My New Metric - Description of what this metric collects
"""

import sqlite3
from pathlib import Path
from typing import Dict, Optional
import oracledb
from .base_metric import BaseMetric


class MyNewMetric(BaseMetric):
    """Collects my custom metric data."""
    
    def _get_display_name(self) -> str:
        return "My New Metric"
    
    def _get_description(self) -> str:
        return "Description of what this metric measures"
    
    def _get_category(self) -> str:
        return "performance"  # or "sessions", "storage", "system"
    
    def collect(self, connection: oracledb.Connection, **kwargs) -> Optional[Dict]:
        """Collect metric data from Oracle."""
        try:
            cursor = connection.cursor()
            
            # Your SQL query here
            query = """
                SELECT col1, col2, col3
                FROM your_view
                WHERE ...
            """
            
            cursor.execute(query)
            
            # Process results
            results = []
            for row in cursor:
                results.append({
                    'col1': row[0],
                    'col2': row[1],
                    'col3': row[2]
                })
            
            cursor.close()
            return {'data': results, 'count': len(results)}
            
        except oracledb.Error as e:
            self.logger.error(f"Error collecting my metric: {e}")
            return None
    
    def _get_storage_schema(self) -> Optional[str]:
        """Define SQLite table schema."""
        return """
            CREATE TABLE IF NOT EXISTS my_metric_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                timestamp TEXT NOT NULL,
                col1 TEXT,
                col2 INTEGER,
                col3 REAL
            )
        """
    
    def _get_storage_indexes(self) -> list:
        """Define SQLite indexes."""
        return [
            "CREATE INDEX IF NOT EXISTS idx_my_metric_ts ON my_metric_history(timestamp)"
        ]
    
    def _store_data_impl(self, db_path: Path, data: Dict, sample_id: str = None):
        """Store data in SQLite."""
        from datetime import datetime
        
        if 'data' not in data:
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        sample_id = sample_id or timestamp
        
        for item in data['data']:
            cursor.execute("""
                INSERT INTO my_metric_history (sample_id, timestamp, col1, col2, col3)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sample_id, timestamp,
                item.get('col1'),
                item.get('col2'),
                item.get('col3')
            ))
        
        conn.commit()
        conn.close()
    
    def render_summary(self, data: Dict) -> Optional[Dict]:
        """Return summary statistics for display."""
        return {
            'Total Items': data.get('count', 0),
            'Custom Stat': 'Some value'
        }
```

### Step 2: Register the metric

Edit `metrics/registry.py` and add your import and registration:

```python
def _auto_discover_metrics(log_dir: Path):
    """Auto-discover and register all metric modules."""
    # ... existing imports ...
    from . import my_new_metric  # Add this line
    
    metrics = [
        # ... existing metrics ...
        my_new_metric.MyNewMetric(log_dir),  # Add this line
    ]
    
    for metric in metrics:
        _registry.register(metric)
```

### Step 3: Done! 🎉

That's it! Your metric will:
- ✅ Automatically appear in the GUI
- ✅ Be collected when monitoring runs
- ✅ Log data to `logs/mynewmetric.jsonl`
- ✅ Store data in SQLite
- ✅ Be available for enable/disable in UI

**No GUI code changes needed!**

---

## 🔧 Advanced Features

### Custom Rendering

Override `render_details()` to provide custom Streamlit visualization:

```python
def render_details(self, data: Dict):
    """Return custom Streamlit visualization."""
    import streamlit as st
    import pandas as pd
    
    if 'data' in data:
        df = pd.DataFrame(data['data'])
        st.dataframe(df)
        st.bar_chart(df['col2'])
```

### Conditional Metrics

Metrics can be dynamically enabled/disabled:

```python
metric = registry.get_metric('MyNewMetric')
metric.enabled = False  # Disable metric
```

### Metric Dependencies

Pass context between metrics via kwargs:

```python
# Collect session overview first
overview = session_overview_metric.collect(connection)

# Pass to dependent metric
details = session_details_metric.collect(connection, overview=overview)
```

---

## 📊 Logging Format

Each metric automatically logs to its own JSONL file:

**Format**: `logs/{metricname}.jsonl`

**Example** (`logs/sessionoverviewmetric.jsonl`):

```json
{"timestamp": "2025-11-17T15:30:00", "metric": "SessionOverviewMetric", "sample_id": "...", "data": {...}}
{"timestamp": "2025-11-17T15:31:00", "metric": "SessionOverviewMetric", "sample_id": "...", "data": {...}}
```

---

## 💾 Storage Format

Each metric stores data in its own SQLite table:

**Database**: `logs/monitor_history.db`

**Tables**:
- `session_overview_history`
- `top_sessions_history`
- `blocking_sessions_history`
- `my_metric_history`
- ... (one per metric)

---

## 🎨 Categories

Metrics are organized by category:

- **sessions** - Session-related metrics
- **performance** - Performance and wait metrics
- **storage** - Disk and tablespace metrics
- **system** - System and host metrics

---

## 🧪 Testing Individual Metrics

Test a metric independently:

```python
from metrics.my_new_metric import MyNewMetric
from pathlib import Path

# Create metric instance
metric = MyNewMetric(log_dir=Path("logs"))

# Test data collection
connection = oracledb.connect(...)
data = metric.collect(connection)
print(data)

# Test logging
metric.log_data(data, sample_id="test-001")

# Test storage
db_path = Path("logs/test.db")
metric.init_storage(db_path)
metric.store_data(db_path, data, sample_id="test-001")
```

---

## 🔍 Querying Historical Data

Query SQLite for historical analysis:

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect("logs/monitor_history.db")

# Query session overview history
df = pd.read_sql_query("""
    SELECT timestamp, total_sessions, active_sessions, blocked_sessions
    FROM session_overview_history
    WHERE timestamp >= datetime('now', '-1 hour')
    ORDER BY timestamp
""", conn)

print(df)
conn.close()
```

---

## 📦 Migration Guide

### Migrating from Old GUI

To migrate the original `oracle_monitor_gui.py`:

1. **Keep existing file for reference**
2. **Gradually refactor** sections to use metric registry
3. **Test each metric** as you migrate it
4. **Update GUI components** to call registry instead of inline code

### Example Migration

**Before** (inline code in GUI):

```python
def get_session_overview(connection):
    cursor = connection.cursor()
    query = "SELECT COUNT(*) FROM v$session ..."
    cursor.execute(query)
    # ... more code ...
    return data
```

**After** (using metrics):

```python
registry = get_registry()
metric = registry.get_metric('SessionOverviewMetric')
data = metric.collect(connection)
```

---

## 🎯 Best Practices

1. **One metric per file** - Keep files focused
2. **Use descriptive names** - `WaitEventsMetric` not `Metric1`
3. **Document SQL queries** - Add comments explaining what queries do
4. **Handle errors gracefully** - Return `None` on errors, log them
5. **Keep metrics independent** - Don't create tight coupling
6. **Test with real data** - Verify on actual Oracle database
7. **Log meaningful data** - Include context for debugging

---

## 🆘 Troubleshooting

### Metric not appearing in GUI

- Check that it's imported in `metrics/registry.py`
- Verify the class inherits from `BaseMetric`
- Check for syntax errors in your metric file

### Data not being collected

- Check database permissions (metric needs SELECT on views)
- Review logs: `logs/{metricname}.jsonl`
- Test metric independently (see Testing section)

### SQLite errors

- Ensure `_get_storage_schema()` returns valid SQL
- Check that column types match data types
- Verify database file permissions

---

## 📚 API Reference

### BaseMetric

Core methods to override:

- `_get_display_name()` - Human-readable name
- `_get_description()` - Metric description
- `_get_category()` - Metric category
- `collect(connection, **kwargs)` - Collect data
- `_get_storage_schema()` - SQLite schema (optional)
- `_get_storage_indexes()` - SQLite indexes (optional)
- `_store_data_impl()` - Storage logic (optional)
- `render_summary()` - Summary view (optional)
- `render_details()` - Detailed view (optional)

### MetricRegistry

Key methods:

- `register(metric)` - Register a metric
- `get_metric(name)` - Get metric by name
- `get_all_metrics()` - Get all metrics
- `get_enabled_metrics()` - Get enabled metrics only
- `collect_all(connection, **kwargs)` - Collect from all enabled
- `log_all(data, sample_id)` - Log all collected data
- `store_all(db_path, data, sample_id)` - Store all data

---

## 🎉 Conclusion

The modular architecture makes it **easy to extend** the Oracle Monitor without modifying core GUI code. Each metric is:

- ✅ Self-contained
- ✅ Independently testable
- ✅ Auto-discovered
- ✅ Easy to add/remove

**Happy monitoring!** 📊

