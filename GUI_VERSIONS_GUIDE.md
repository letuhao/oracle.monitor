# Oracle Monitor - GUI Versions Guide

## 📚 Three Versions Explained

---

## 1️⃣ `oracle_monitor_gui.py` - **Original (Full-Featured, Monolithic)**

### ✅ Pros
- **Complete features**: Connection UI, auto-refresh, alerts, charts, export
- **Battle-tested**: Used in production
- **Stable**: All bugs fixed

### ❌ Cons
- **3,221 lines**: Hard to maintain
- **Monolithic**: One massive file
- **Merge conflicts**: Team can't work in parallel
- **Hard to extend**: Adding metrics requires editing main file

### When to Use
- ✅ You need a stable, production-ready solution **NOW**
- ✅ You're working alone
- ✅ You don't plan to add many new metrics

### Run It
```bash
streamlit run oracle_monitor_gui.py
```

---

## 2️⃣ `oracle_monitor_modular.py` - **Simple Example (Educational)**

### ✅ Pros
- **Clean code**: Shows modular pattern
- **Easy to understand**: Simple example
- **Extensible**: Easy to add metrics

### ❌ Cons
- **Missing features**: No connection UI, no auto-refresh, no alerts, no charts
- **Not production-ready**: Just a demo
- **Basic UI**: Minimal functionality

### When to Use
- ✅ Learning how the modular system works
- ✅ Understanding the metric registry
- ✅ Quick testing of new metrics

### Run It
```bash
streamlit run oracle_monitor_modular.py
```

---

## 3️⃣ `oracle_monitor_gui_v2.py` - **New Full-Featured Modular** ⭐ RECOMMENDED

### ✅ Pros
- **All features**: Connection UI, auto-refresh, alerts, charts
- **Modular architecture**: Uses metric registry
- **Extensible**: Add metrics by just creating a new file
- **Team-friendly**: No merge conflicts
- **Better UI**: Improved organization
- **Production-ready**: All features included

### ❌ Cons
- **New code**: Needs testing
- **Requires dependencies**: plotly, pandas (same as original)

### When to Use
- ✅ **Best choice for most users** ⭐
- ✅ You want all features + extensibility
- ✅ You plan to add new metrics
- ✅ Multiple people working on the code
- ✅ You want modern, maintainable code

### Run It
```bash
streamlit run oracle_monitor_gui_v2.py
```

---

## 🔄 Feature Comparison Table

| Feature | Original | Modular (Simple) | **V2 (Full)** |
|---------|----------|------------------|---------------|
| **Connection UI** | ✅ | ❌ | ✅ |
| **Auto-refresh** | ✅ | ❌ | ✅ |
| **Start/Stop** | ✅ | ❌ | ✅ |
| **Alert config** | ✅ | ❌ | ✅ |
| **Charts** | ✅ | ❌ | ✅ |
| **Multiple tabs** | ✅ | ❌ | ✅ |
| **Metric selection** | ❌ | ✅ | ✅ |
| **Modular code** | ❌ | ✅ | ✅ |
| **Easy to extend** | ❌ | ✅ | ✅ |
| **Lines of code** | 3,221 | 190 | 650 |
| **Production ready** | ✅ | ❌ | ✅ |

---

## 🎯 Quick Decision Guide

### Choose **Original** if:
- ❓ Need it working **today** without testing
- ❓ Already using it in production
- ❓ Don't plan to modify code

### Choose **Modular (Simple)** if:
- ❓ Learning the system
- ❓ Quick testing only
- ❓ Building your own custom GUI

### Choose **V2 (Full)** if: ⭐
- ✅ Want all features
- ✅ Plan to add metrics
- ✅ Working in a team
- ✅ Want maintainable code
- ✅ Starting a new deployment

---

## 🚀 Getting Started with V2

### 1. Install Dependencies

Already installed if you were using the original:

```bash
pip install streamlit oracledb pandas plotly
```

### 2. Run V2

```bash
streamlit run oracle_monitor_gui_v2.py
```

### 3. Configure Connection

In the sidebar:
1. Click "🔌 Database Connection"
2. Fill in: Host, Port, Service Name, Username, Password
3. Click "🧪 Test" to test connection
4. Click "🔌 Connect" to connect

### 4. Start Monitoring

1. Set refresh interval (5-300 seconds)
2. Click "▶️ Start" to begin auto-monitoring
3. Or click "🔄 Collect Now" for manual collection

### 5. Configure Alerts

1. Click "🚨 Alert Thresholds" in sidebar
2. Set thresholds for:
   - Max Sessions
   - Max Active Sessions
   - Max Blocked Sessions
   - Max Tablespace %

### 6. Select Metrics

In sidebar under "📊 Metrics":
1. Choose category (or "All")
2. Check/uncheck metrics to enable/disable

---

## 📊 V2 Features Explained

### Connection Management
- **UI Form**: Enter connection details in the UI
- **Test Connection**: Test before connecting
- **Save Config**: Loads from `config.json` by default
- **Connection Status**: Always visible in sidebar

### Auto-Refresh Monitoring
- **Interval**: 5-300 seconds (configurable)
- **Start/Stop**: Control monitoring
- **Manual Collect**: Force immediate collection
- **Countdown**: Shows time until next collection

### Alerts
- **Configurable Thresholds**: Set your own limits
- **Real-time Alerts**: Shows warnings/critical alerts
- **Logged**: All alerts logged to files

### Multiple Tabs
1. **📊 Overview**: Key metrics and host stats
2. **👥 Sessions**: Top sessions and blocking sessions
3. **💾 Storage**: Tablespace and temp usage
4. **⚡ Performance**: Wait events and I/O

### Charts
- **Tablespace Usage**: Bar chart of top 10
- **Wait Events**: Top 10 wait events
- **Metrics**: Color-coded by severity

### Metric Selection
- **Category Filter**: View by category
- **Enable/Disable**: Choose which to collect
- **Dynamic**: Only collects enabled metrics

---

## 🔧 Adding New Metrics to V2

Same as modular system - just create a new file:

### 1. Create `metrics/my_metric.py`

```python
from metrics.base_metric import BaseMetric

class MyMetric(BaseMetric):
    def _get_display_name(self):
        return "My Custom Metric"
    
    def _get_description(self):
        return "Description of what this collects"
    
    def _get_category(self):
        return "performance"
    
    def _collect_data(self, connection):
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM my_view")
        return {'data': cursor.fetchall()}
```

### 2. Restart V2

The new metric will automatically appear in the sidebar!

No need to edit `oracle_monitor_gui_v2.py` - it uses the registry.

---

## 🎨 Customizing V2

### Change Colors

Edit the Streamlit theme in `.streamlit/config.toml`:

```toml
[theme]
primaryColor="#FF4B4B"
backgroundColor="#FFFFFF"
secondaryBackgroundColor="#F0F2F6"
textColor="#262730"
font="sans serif"
```

### Add More Tabs

In `oracle_monitor_gui_v2.py`, add to the tabs list:

```python
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview", 
    "👥 Sessions", 
    "💾 Storage", 
    "⚡ Performance",
    "📈 My Custom Tab"  # Add this
])

with tab5:
    render_my_custom_tab(results)  # Create this function
```

### Change Auto-Refresh Range

Line 179 in `oracle_monitor_gui_v2.py`:

```python
interval = st.sidebar.slider(
    "Refresh Interval (seconds)",
    min_value=5,      # Change minimum
    max_value=300,    # Change maximum
    value=60,         # Change default
    step=5
)
```

---

## 📝 Migration Path

### From Original → V2

1. **No code changes needed** - V2 uses the same metric registry
2. **Same database schema** - Uses same SQLite tables
3. **Same log format** - Compatible with existing logs

Just switch the command:
```bash
# Old
streamlit run oracle_monitor_gui.py

# New
streamlit run oracle_monitor_gui_v2.py
```

All your existing data, logs, and database will work!

---

## 🐛 Troubleshooting V2

### "No module named 'metrics'"

You need the metrics folder in the same directory:
```
oracle.monitor/
├── metrics/
│   ├── __init__.py
│   ├── base_metric.py
│   ├── registry.py
│   └── *.py (all metric files)
└── oracle_monitor_gui_v2.py
```

### "Connection failed"

1. Check credentials in sidebar form
2. Use "🧪 Test" button first
3. Check `config.json` if using file config
4. Verify Oracle database is accessible

### Auto-refresh not working

1. Make sure you clicked "▶️ Start"
2. Check if "🟢 Monitoring Active" shows in UI
3. Look for countdown timer showing next refresh

### Metrics not appearing

1. Check sidebar - metrics might be disabled
2. Verify metric files in `metrics/` folder
3. Check category filter (try "All")

---

## 💡 Tips

### Save Connection Profile

Create `config.json` to avoid typing credentials:

```json
{
  "database": {
    "host": "your-db-server",
    "port": 1521,
    "service_name": "ORCL",
    "username": "monitor_user",
    "password": "your_password"
  }
}
```

V2 will load this automatically!

### Optimize Performance

1. **Disable unused metrics**: Uncheck them in sidebar
2. **Increase interval**: For less frequent collection
3. **Select specific category**: Don't collect all metrics

### View Logs

All data is still logged:
- `logs/app.log` - Application events
- `logs/metrics.jsonl` - All metrics (JSON Lines)
- `logs/monitor_history.db` - SQLite database

---

## 🎉 Summary

### Use **V2** for:
- ✅ Production deployments
- ✅ Team development
- ✅ Extensible monitoring
- ✅ Modern, maintainable code

### Keep **Original** for:
- ✅ Existing deployments (don't break what works)
- ✅ Reference/comparison

### Use **Modular (Simple)** for:
- ✅ Learning
- ✅ Quick testing

---

**Recommended**: Start with **V2** (`oracle_monitor_gui_v2.py`) for the best experience! ⭐

