# Quick Start Guide - Oracle Monitor GUI

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies

```bash
cd dwh-monitor
pip install -r requirements.txt
```

This installs:
- `oracledb` - Oracle database connector
- `streamlit` - Web GUI framework
- `pandas` - Data processing
- `plotly` - Interactive charts

### Step 2: Run the GUI

**Windows:**
```bash
run_gui.bat
```

**Linux/Mac:**
```bash
chmod +x run_gui.sh
./run_gui.sh
```

**Or manually:**
```bash
streamlit run oracle_monitor_gui.py
```

### Step 3: Connect to Database

1. The web interface will open automatically in your browser (usually `http://localhost:8501`)
2. In the sidebar, enter your Oracle database connection details:
   - **Host**: Your Oracle server hostname/IP
   - **Port**: Usually 1521
   - **Service Name**: Your Oracle service name (e.g., ORCL)
   - **Username**: Database username
   - **Password**: Database password
3. Click **"🔌 Connect"** button
4. Once connected, click **"▶️ Start Monitoring"** to begin

## 📊 Using the Dashboard

### Main Dashboard

- **Key Metrics**: Total sessions, active sessions, blocked sessions, CPU time
- **Session Status Chart**: Pie chart showing active vs inactive sessions
- **Resource Usage Chart**: Bar chart showing logical/physical reads
- **Historical Trends**: Line charts showing session and I/O trends over time

### Tabs

1. **🔝 Top Sessions**: Shows top 20 resource-consuming sessions
   - Sorted by logical reads
   - Shows CPU time, wait events, SQL IDs

2. **🔒 Blocking Sessions**: Lists all blocking/blocked sessions
   - Shows which sessions are blocking others
   - Displays wait times

3. **📋 Current Overview**: Current session statistics
   - Export history to CSV button

### Controls

- **▶️ Start Monitoring**: Begin continuous monitoring (auto-refresh)
- **⏸️ Stop Monitoring**: Stop auto-refresh
- **🔄 Refresh Now**: Manual refresh of current data
- **🗑️ Clear History**: Clear historical data
- **🔌 Disconnect**: Close database connection

## 🔧 Troubleshooting

### Port Already in Use

If port 8501 is already in use, Streamlit will use the next available port. Check the terminal output for the actual URL.

### Connection Failed

1. Verify database credentials
2. Check network connectivity: `ping oracle_host`
3. Test with SQL*Plus: `sqlplus username/password@host:port/service_name`
4. Ensure Oracle listener is running

### No Data Showing

1. Check database user has SELECT privileges on V$ views
2. Verify there are active sessions (check with SQL*Plus)
3. Check browser console for errors (F12)

### GUI Not Opening

1. Check if Streamlit is installed: `pip show streamlit`
2. Try manual start: `streamlit run oracle_monitor_gui.py --server.port 8501`
3. Check firewall settings

## 💡 Tips

- **Auto-refresh**: When monitoring is active, the page refreshes every 5 seconds
- **Export Data**: Use the "Export History to CSV" button in the Current Overview tab
- **Multiple Windows**: You can open multiple browser tabs for different views
- **Mobile Friendly**: The dashboard works on tablets and phones too!

## 📝 Notes

- All queries are **READ-ONLY** - no data modification
- Historical data is kept in memory (last 100 records)
- Export CSV to save data permanently
- Connection credentials are stored in browser session only

## 🆘 Need Help?

Check the main [README.md](README.md) for:
- Detailed configuration options
- Database permission requirements
- Advanced troubleshooting
- Security best practices

