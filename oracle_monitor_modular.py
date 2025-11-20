#!/usr/bin/env python3
"""
Oracle Database Session Monitor - Modular Architecture Example

This is a simplified example showing how to use the new modular metric system.
The original oracle_monitor_gui.py can be refactored to use this pattern.
"""

import os
import json
import oracledb
import streamlit as st
from pathlib import Path
from datetime import datetime

# Import the metrics system
from metrics import get_registry

# Configure page
st.set_page_config(
    page_title="Oracle Monitor (Modular)",
    page_icon="📊",
    layout="wide"
)

# Initialize paths
LOG_DIR = Path("logs")
DB_PATH = LOG_DIR / "monitor_history.db"


def load_config(config_path: str = None):
    """Load configuration from file or environment variable."""
    config_path = config_path or os.getenv('ORACLE_MONITOR_CONFIG', 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Configuration file not found: {config_path}")
        return None


def connect_database(db_config):
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
        st.error(f"Database connection failed: {e}")
        return None


def initialize_storage(registry):
    """Initialize SQLite storage for all metrics."""
    for metric in registry.get_all_metrics():
        metric.init_storage(DB_PATH)


def main():
    """Main application."""
    st.title("📊 Oracle Database Monitor (Modular Architecture)")
    
    # Sidebar configuration
    st.sidebar.header("Configuration")
    
    # Load config
    config = load_config()
    if not config:
        st.stop()
    
    # Get registry (auto-discovers all metrics)
    registry = get_registry(LOG_DIR)
    
    # Initialize storage
    initialize_storage(registry)
    
    # Connect to database
    if 'connection' not in st.session_state or st.sidebar.button("Reconnect"):
        connection = connect_database(config['database'])
        if connection:
            st.session_state.connection = connection
            st.sidebar.success("✅ Connected")
        else:
            st.stop()
    
    connection = st.session_state.connection
    
    # Sidebar: Metric selection
    st.sidebar.header("Metrics")
    
    categories = sorted(registry.categories.keys())
    selected_category = st.sidebar.selectbox("Category", ["All"] + categories)
    
    # Get metrics to display
    if selected_category == "All":
        metrics_to_show = registry.get_enabled_metrics()
    else:
        metrics_to_show = registry.get_metrics_by_category(selected_category)
    
    # Display metric toggles
    for metric in metrics_to_show:
        metric.enabled = st.sidebar.checkbox(
            metric.display_name,
            value=metric.enabled,
            help=metric.description
        )
    
    # Main content area
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header("Metrics Collection")
    
    with col2:
        if st.button("🔄 Collect Now", type="primary"):
            with st.spinner("Collecting metrics..."):
                # Generate sample ID
                sample_id = datetime.now().isoformat()
                
                # Collect all enabled metrics
                results = registry.collect_all(connection)
                
                # Log all metrics
                registry.log_all(results, sample_id)
                
                # Store all metrics
                registry.store_all(DB_PATH, results, sample_id)
                
                st.success(f"✅ Collected {len(results)} metrics")
                st.session_state['last_results'] = results
                st.session_state['last_sample_id'] = sample_id
    
    # Display results
    if 'last_results' in st.session_state:
        results = st.session_state['last_results']
        
        st.divider()
        
        # Group metrics by category
        for category in categories:
            category_metrics = [m for m in metrics_to_show if m.category == category and m.enabled]
            
            if not category_metrics:
                continue
            
            st.subheader(f"📂 {category.title()}")
            
            # Display each metric in this category
            for metric in category_metrics:
                metric_name = metric.name
                
                if metric_name not in results:
                    continue
                
                data = results[metric_name]
                
                with st.expander(f"**{metric.display_name}** - {metric.description}", expanded=True):
                    # Display summary if available
                    summary = metric.render_summary(data)
                    if summary:
                        cols = st.columns(len(summary))
                        for i, (key, value) in enumerate(summary.items()):
                            cols[i].metric(key, value)
                    
                    # Display raw data (you can customize this per metric)
                    if st.checkbox(f"Show raw data for {metric.display_name}", key=f"raw_{metric_name}"):
                        st.json(data)
    
    # Sidebar: Statistics
    st.sidebar.divider()
    st.sidebar.header("Statistics")
    st.sidebar.metric("Total Metrics", len(registry.get_all_metrics()))
    st.sidebar.metric("Enabled Metrics", len(registry.get_enabled_metrics()))
    
    if 'last_sample_id' in st.session_state:
        st.sidebar.caption(f"Last sample: {st.session_state['last_sample_id']}")


if __name__ == '__main__':
    main()

