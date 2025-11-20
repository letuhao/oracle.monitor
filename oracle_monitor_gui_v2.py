#!/usr/bin/env python3
"""
Oracle Database Session Monitor - Full-Featured Modular GUI (V2)

This version combines:
- Modular architecture (metric registry)
- Full features from original GUI
- Improved UI/UX
- Auto-refresh monitoring
- Alert configuration
- Charts and visualizations
"""

import json
import time
import oracledb
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

# Import the metrics system
from metrics import get_registry

# Configure page
st.set_page_config(
    page_title="Oracle Monitor V2",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize paths
LOG_DIR = Path("logs")
DB_PATH = LOG_DIR / "monitor_history.db"

# Initialize session state
if 'monitoring_active' not in st.session_state:
    st.session_state.monitoring_active = False
if 'connection' not in st.session_state:
    st.session_state.connection = None
if 'last_results' not in st.session_state:
    st.session_state.last_results = {}
if 'history' not in st.session_state:
    st.session_state.history = []


def connect_database(db_config: Dict) -> Optional[oracledb.Connection]:
    """Establish database connection."""
    try:
        dsn = oracledb.makedsn(
            db_config['host'],
            db_config['port'],
            service_name=db_config['service_name']
        )
        
        connection = oracledb.connect(
            user=db_config['username'],
            password=db_config['password'],
            dsn=dsn
        )
        return connection
    except oracledb.Error as e:
        st.error(f"❌ Connection failed: {e}")
        return None


def initialize_storage(registry):
    """Initialize SQLite storage for all metrics."""
    for metric in registry.get_all_metrics():
        metric.init_storage(DB_PATH)


def collect_metrics(registry, connection, sample_id: str = None):
    """Collect all enabled metrics."""
    sample_id = sample_id or datetime.now().isoformat()
    
    # Collect all enabled metrics
    results = registry.collect_all(connection)
    
    # Log all metrics
    registry.log_all(results, sample_id)
    
    # Store all metrics
    registry.store_all(DB_PATH, results, sample_id)
    
    return results, sample_id


def check_alerts(results: Dict, thresholds: Dict) -> list:
    """Check for alert conditions."""
    alerts = []
    
    # Check session overview alerts
    if 'SessionOverviewMetric' in results:
        overview = results['SessionOverviewMetric']
        
        if overview.get('total_sessions', 0) >= thresholds.get('max_sessions', 500):
            alerts.append({
                'level': 'WARNING',
                'message': f"Total sessions ({overview['total_sessions']}) exceeds threshold"
            })
        
        if overview.get('active_sessions', 0) >= thresholds.get('max_active_sessions', 200):
            alerts.append({
                'level': 'WARNING',
                'message': f"Active sessions ({overview['active_sessions']}) exceeds threshold"
            })
        
        if overview.get('blocked_sessions', 0) >= thresholds.get('max_blocked_sessions', 10):
            alerts.append({
                'level': 'CRITICAL',
                'message': f"Blocked sessions ({overview['blocked_sessions']}) exceeds threshold"
            })
    
    # Check tablespace alerts
    if 'TablespaceUsageMetric' in results:
        ts_data = results['TablespaceUsageMetric']
        if 'tablespaces' in ts_data:
            for ts in ts_data['tablespaces']:
                if ts.get('pct_used', 0) >= thresholds.get('max_tablespace_pct', 90):
                    alerts.append({
                        'level': 'WARNING',
                        'message': f"Tablespace {ts['tablespace']} at {ts['pct_used']:.1f}% full"
                    })
    
    return alerts


def sidebar_configuration():
    """Render sidebar with configuration options."""
    st.sidebar.title("⚙️ Configuration")
    
    # Connection Form
    with st.sidebar.expander("🔌 Database Connection", expanded=False):
        # Load existing config if available
        default_config = {
            'host': 'localhost',
            'port': 1521,
            'service_name': 'ORCL',
            'username': '',
            'password': ''
        }
        
        # Try to load from file
        try:
            with open('config.json', 'r') as f:
                loaded = json.load(f)
                if 'database' in loaded:
                    default_config.update(loaded['database'])
        except:
            pass
        
        with st.form("connection_form"):
            host = st.text_input("Host", value=default_config['host'])
            port = st.number_input("Port", value=default_config['port'], min_value=1, max_value=65535)
            service = st.text_input("Service Name", value=default_config['service_name'])
            username = st.text_input("Username", value=default_config['username'])
            password = st.text_input("Password", value=default_config['password'], type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                connect_btn = st.form_submit_button("🔌 Connect", use_container_width=True)
            with col2:
                test_btn = st.form_submit_button("🧪 Test", use_container_width=True)
        
        if connect_btn or test_btn:
            db_config = {
                'host': host,
                'port': int(port),
                'service_name': service,
                'username': username,
                'password': password
            }
            
            with st.spinner("Connecting..."):
                connection = connect_database(db_config)
                
                if connection:
                    if test_btn:
                        st.success("✅ Connection test successful!")
                        connection.close()
                    else:
                        st.session_state.connection = connection
                        st.session_state.db_config = db_config
                        st.success("✅ Connected!")
                        st.rerun()
    
    # Connection Status
    if st.session_state.connection:
        db_config = st.session_state.get('db_config', {})
        st.sidebar.success(f"✅ Connected to {db_config.get('host', 'database')}")
        if st.sidebar.button("🔌 Disconnect"):
            if st.session_state.connection:
                st.session_state.connection.close()
            st.session_state.connection = None
            st.rerun()
    else:
        st.sidebar.warning("⚠️ Not connected")
    
    st.sidebar.divider()
    
    # Monitoring Controls
    st.sidebar.header("📡 Monitoring Controls")
    
    # Refresh interval
    interval = st.sidebar.slider(
        "Refresh Interval (seconds)",
        min_value=5,
        max_value=300,
        value=st.session_state.get('refresh_interval', 60),
        step=5,
        help="How often to collect metrics"
    )
    st.session_state.refresh_interval = interval
    
    # Start/Stop buttons
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("▶️ Start", use_container_width=True, disabled=st.session_state.monitoring_active):
            if st.session_state.connection:
                st.session_state.monitoring_active = True
                st.session_state.last_collect_time = 0  # Force immediate collection
                st.rerun()
            else:
                st.error("Connect first!")
    
    with col2:
        if st.button("⏸️ Stop", use_container_width=True, disabled=not st.session_state.monitoring_active):
            st.session_state.monitoring_active = False
            st.rerun()
    
    # Manual collect
    if st.sidebar.button("🔄 Collect Now", use_container_width=True, disabled=not st.session_state.connection):
        st.session_state.force_collect = True
    
    st.sidebar.divider()
    
    # Alert Configuration
    with st.sidebar.expander("🚨 Alert Thresholds", expanded=False):
        st.session_state.alert_thresholds = {
            'max_sessions': st.number_input("Max Sessions", value=500, min_value=1),
            'max_active_sessions': st.number_input("Max Active Sessions", value=200, min_value=1),
            'max_blocked_sessions': st.number_input("Max Blocked Sessions", value=10, min_value=1),
            'max_tablespace_pct': st.slider("Max Tablespace %", value=90, min_value=50, max_value=100)
        }
    
    st.sidebar.divider()
    
    # Metric Selection
    st.sidebar.header("📊 Metrics")
    registry = get_registry(LOG_DIR)
    
    # Category filter
    categories = sorted(registry.categories.keys())
    selected_category = st.sidebar.selectbox("Category", ["All"] + categories)
    
    # Get metrics to show
    if selected_category == "All":
        metrics_to_show = registry.get_all_metrics()
    else:
        metrics_to_show = registry.get_metrics_by_category(selected_category)
    
    # Metric toggles
    st.sidebar.caption("Select metrics to collect:")
    for metric in metrics_to_show:
        metric.enabled = st.sidebar.checkbox(
            metric.display_name,
            value=metric.enabled,
            key=f"metric_{metric.name}",
            help=metric.description
        )
    
    return registry


def render_overview_tab(results: Dict):
    """Render overview tab with key metrics."""
    st.header("📊 Overview")
    
    # Check if we have session overview data
    if 'SessionOverviewMetric' in results:
        overview = results['SessionOverviewMetric']
        
        # Key metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Sessions",
                overview.get('total_sessions', 0),
                help="Total database sessions"
            )
        
        with col2:
            st.metric(
                "Active Sessions",
                overview.get('active_sessions', 0),
                help="Currently active sessions"
            )
        
        with col3:
            blocked = overview.get('blocked_sessions', 0)
            st.metric(
                "Blocked Sessions",
                blocked,
                delta=f"-{blocked}" if blocked > 0 else None,
                delta_color="inverse",
                help="Sessions waiting on locks"
            )
        
        with col4:
            st.metric(
                "CPU (seconds)",
                f"{overview.get('cpu_seconds', 0):.1f}",
                help="Total CPU time"
            )
        
        # Additional metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Logical Reads (MB)",
                f"{overview.get('logical_reads_mb', 0):.1f}"
            )
        
        with col2:
            st.metric(
                "Physical Reads (MB)",
                f"{overview.get('physical_reads_mb', 0):.1f}"
            )
        
        with col3:
            inactive = overview.get('inactive_sessions', 0)
            st.metric(
                "Inactive Sessions",
                inactive
            )
    
    else:
        st.info("ℹ️ No session overview data collected yet")
    
    # Host metrics if available
    if 'HostMetricsMetric' in results:
        st.subheader("🖥️ Host Metrics")
        host_metrics = results['HostMetricsMetric']
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cpu = host_metrics.get('cpu_percent', 0)
            st.metric("CPU %", f"{cpu:.1f}%")
        
        with col2:
            mem = host_metrics.get('memory_percent', 0)
            st.metric("Memory %", f"{mem:.1f}%")
        
        with col3:
            st.metric("CPU Cores", host_metrics.get('cpu_count', 0))
        
        with col4:
            swap = host_metrics.get('swap_percent', 0)
            st.metric("Swap %", f"{swap:.1f}%")


def render_sessions_tab(results: Dict):
    """Render sessions tab with top and blocking sessions."""
    st.header("👥 Sessions")
    
    # Top Sessions
    if 'TopSessionsMetric' in results:
        st.subheader("🔝 Top Sessions by Logical Reads")
        top_data = results['TopSessionsMetric']
        
        if 'sessions' in top_data and top_data['sessions']:
            df = pd.DataFrame(top_data['sessions'])
            df = df[['sid', 'username', 'program', 'status', 'logical_reads_mb', 'cpu_seconds', 'sql_id']]
            st.dataframe(df, use_container_width=True, height=300)
        else:
            st.info("No session data available")
    
    # Blocking Sessions
    if 'BlockingSessionsMetric' in results:
        st.subheader("🔒 Blocking Sessions")
        blocking_data = results['BlockingSessionsMetric']
        
        if 'blocking_sessions' in blocking_data and blocking_data['blocking_sessions']:
            df = pd.DataFrame(blocking_data['blocking_sessions'])
            st.dataframe(df, use_container_width=True, height=300)
            
            # Alert if blocking detected
            if len(blocking_data['blocking_sessions']) > 0:
                st.warning(f"⚠️ {len(blocking_data['blocking_sessions'])} blocking session(s) detected!")
        else:
            st.success("✅ No blocking sessions detected")


def render_storage_tab(results: Dict):
    """Render storage tab with tablespace and temp usage."""
    st.header("💾 Storage")
    
    # Tablespace Usage
    if 'TablespaceUsageMetric' in results:
        st.subheader("📦 Tablespace Usage")
        ts_data = results['TablespaceUsageMetric']
        
        if 'tablespaces' in ts_data and ts_data['tablespaces']:
            df = pd.DataFrame(ts_data['tablespaces'])
            
            # Show table
            display_df = df[['tablespace', 'type', 'used_mb', 'allocated_mb', 'pct_used', 'free_mb']]
            st.dataframe(display_df, use_container_width=True, height=300)
            
            # Chart - Top 10 by usage
            if len(df) > 0:
                chart_df = df.nlargest(10, 'pct_used')
                fig = px.bar(
                    chart_df,
                    x='tablespace',
                    y='pct_used',
                    title='Top 10 Tablespaces by Usage %',
                    color='pct_used',
                    color_continuous_scale='RdYlGn_r'
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No tablespace data available")
    
    # Temp Usage
    if 'TempUsageMetric' in results:
        st.subheader("🌡️ Temp Tablespace Usage")
        temp_data = results['TempUsageMetric']
        
        if 'temp_usage' in temp_data and temp_data['temp_usage']:
            df = pd.DataFrame(temp_data['temp_usage'])
            st.dataframe(df, use_container_width=True, height=200)
        else:
            st.success("✅ No temp tablespace usage")


def render_performance_tab(results: Dict):
    """Render performance tab with wait events and I/O."""
    st.header("⚡ Performance")
    
    # Wait Events
    if 'WaitEventsMetric' in results:
        st.subheader("⏱️ Wait Events")
        wait_data = results['WaitEventsMetric']
        
        if 'wait_events' in wait_data and wait_data['wait_events']:
            df = pd.DataFrame(wait_data['wait_events'])
            
            # Table
            st.dataframe(df, use_container_width=True, height=300)
            
            # Chart - Top 10 wait events
            if len(df) > 0:
                chart_df = df.nlargest(10, 'total_wait_seconds')
                fig = px.bar(
                    chart_df,
                    x='event',
                    y='total_wait_seconds',
                    title='Top 10 Wait Events',
                    color='total_wait_seconds',
                    color_continuous_scale='Reds'
                )
                fig.update_xaxes(tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No wait events data available")
    
    # I/O Sessions
    if 'IOSessionsMetric' in results:
        st.subheader("💿 I/O Sessions")
        io_data = results['IOSessionsMetric']
        
        if 'io_sessions' in io_data and io_data['io_sessions']:
            df = pd.DataFrame(io_data['io_sessions'])
            st.dataframe(df, use_container_width=True, height=300)
        else:
            st.info("No I/O data available")


def main():
    """Main application."""
    st.title("📊 Oracle Database Monitor V2")
    st.caption("Full-featured modular monitoring with auto-refresh")
    
    # Initialize registry and storage
    registry = get_registry(LOG_DIR)
    initialize_storage(registry)
    
    # Sidebar configuration
    registry = sidebar_configuration()
    
    # Auto-refresh logic
    if st.session_state.monitoring_active and st.session_state.connection:
        current_time = time.time()
        last_collect = st.session_state.get('last_collect_time', 0)
        interval = st.session_state.get('refresh_interval', 60)
        
        if current_time - last_collect >= interval:
            # Time to collect
            with st.spinner("🔄 Collecting metrics..."):
                results, sample_id = collect_metrics(registry, st.session_state.connection)
                st.session_state.last_results = results
                st.session_state.last_sample_id = sample_id
                st.session_state.last_collect_time = current_time
                
                # Check alerts
                thresholds = st.session_state.get('alert_thresholds', {})
                alerts = check_alerts(results, thresholds)
                st.session_state.alerts = alerts
            
            st.rerun()
    
    # Manual collect
    if st.session_state.get('force_collect', False) and st.session_state.connection:
        with st.spinner("🔄 Collecting metrics..."):
            results, sample_id = collect_metrics(registry, st.session_state.connection)
            st.session_state.last_results = results
            st.session_state.last_sample_id = sample_id
            st.session_state.last_collect_time = time.time()
            
            # Check alerts
            thresholds = st.session_state.get('alert_thresholds', {})
            alerts = check_alerts(results, thresholds)
            st.session_state.alerts = alerts
        
        st.session_state.force_collect = False
        st.rerun()
    
    # Display monitoring status
    status_col1, status_col2, status_col3 = st.columns([2, 2, 1])
    
    with status_col1:
        if st.session_state.monitoring_active:
            st.success("🟢 Monitoring Active")
        else:
            st.info("⚪ Monitoring Stopped")
    
    with status_col2:
        if 'last_sample_id' in st.session_state:
            last_time = st.session_state.get('last_collect_time', 0)
            if last_time > 0:
                time_ago = time.time() - last_time
                st.caption(f"Last collect: {int(time_ago)}s ago")
    
    with status_col3:
        # Next refresh countdown
        if st.session_state.monitoring_active:
            next_refresh = st.session_state.get('refresh_interval', 60) - int(time.time() - st.session_state.get('last_collect_time', 0))
            if next_refresh > 0:
                st.caption(f"Next: {next_refresh}s")
    
    # Display alerts
    if 'alerts' in st.session_state and st.session_state.alerts:
        st.divider()
        st.subheader("🚨 Alerts")
        for alert in st.session_state.alerts:
            if alert['level'] == 'CRITICAL':
                st.error(f"🔴 {alert['message']}")
            else:
                st.warning(f"🟡 {alert['message']}")
        st.divider()
    
    # Main content with tabs
    if not st.session_state.connection:
        st.warning("⚠️ Please connect to a database using the sidebar")
        st.stop()
    
    if not st.session_state.last_results:
        st.info("ℹ️ Click 'Collect Now' or start monitoring to see data")
        st.stop()
    
    # Render tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "👥 Sessions", "💾 Storage", "⚡ Performance"])
    
    results = st.session_state.last_results
    
    with tab1:
        render_overview_tab(results)
    
    with tab2:
        render_sessions_tab(results)
    
    with tab3:
        render_storage_tab(results)
    
    with tab4:
        render_performance_tab(results)
    
    # Footer with statistics
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Metrics", len(registry.get_all_metrics()))
    
    with col2:
        st.metric("Enabled Metrics", len(registry.get_enabled_metrics()))
    
    with col3:
        if 'last_sample_id' in st.session_state:
            st.caption(f"Sample: {st.session_state.last_sample_id[:19]}")
    
    with col4:
        st.caption(f"Interval: {st.session_state.get('refresh_interval', 60)}s")


if __name__ == '__main__':
    main()

