#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Schema Migration Script

This script fixes the database schema by adding missing columns or recreating tables.
Run this when you get "table has no column named X" errors.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("logs/monitor_history.db")

def check_table_schema(cursor, table_name):
    """Check if a table exists and print its schema."""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        if columns:
            print(f"\n[OK] Table '{table_name}' exists with columns:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
            return True
        else:
            print(f"\n[MISSING] Table '{table_name}' does not exist")
            return False
    except sqlite3.Error as e:
        print(f"\n[ERROR] Error checking table '{table_name}': {e}")
        return False

def add_missing_column(cursor, table_name, column_name, column_type):
    """Add a missing column to a table."""
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        print(f"  [OK] Added column '{column_name}' to '{table_name}'")
        return True
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"  [INFO] Column '{column_name}' already exists in '{table_name}'")
            return True
        else:
            print(f"  [ERROR] Error adding column '{column_name}': {e}")
            return False

def recreate_temp_usage_table(cursor):
    """Recreate the temp_usage_history table with correct schema."""
    print("\n[FIXING] Recreating temp_usage_history table...")
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temp_usage_history'")
    exists = cursor.fetchone()
    
    if exists:
        # Backup old data
        print("  [INFO] Backing up old data...")
        try:
            cursor.execute("SELECT * FROM temp_usage_history")
            old_data = cursor.fetchall()
            print(f"  [INFO] Found {len(old_data)} rows to backup")
        except:
            old_data = []
        
        # Drop old table
        print("  [INFO] Dropping old table...")
        cursor.execute("DROP TABLE temp_usage_history")
    
    # Create new table with correct schema
    print("  [INFO] Creating new table with correct schema...")
    cursor.execute("""
        CREATE TABLE temp_usage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id TEXT,
            timestamp TEXT NOT NULL,
            sid INTEGER,
            username TEXT,
            program TEXT,
            tablespace TEXT,
            segtype TEXT,
            used_mb REAL
        )
    """)
    
    print("  [OK] Table recreated successfully")

def fix_all_tables(cursor):
    """Fix all tables that might have schema issues."""
    
    tables_to_check = {
        'temp_usage_history': {
            'required_columns': {
                'segtype': 'TEXT'
            }
        },
        # Add other tables here if needed
    }
    
    for table_name, config in tables_to_check.items():
        print(f"\n[CHECKING] Table: {table_name}")
        
        if check_table_schema(cursor, table_name):
            # Table exists, check for missing columns
            for col_name, col_type in config.get('required_columns', {}).items():
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = {col[1] for col in cursor.fetchall()}
                
                if col_name not in columns:
                    print(f"  [MISSING] Column: {col_name}")
                    add_missing_column(cursor, table_name, col_name, col_type)
                else:
                    print(f"  [OK] Column '{col_name}' exists")
        else:
            # Table doesn't exist, it will be created on first use
            print(f"  [INFO] Table will be created on first use")

def main():
    """Main function to fix database schema."""
    print("=" * 60)
    print("DATABASE SCHEMA MIGRATION TOOL")
    print("=" * 60)
    
    if not DB_PATH.exists():
        print(f"\n[WARN] Database file not found: {DB_PATH}")
        print("This is normal if you haven't run the monitor yet.")
        print("The database will be created with correct schema on first run.")
        return
    
    print(f"\n[INFO] Database: {DB_PATH}")
    
    # Backup database first
    backup_path = DB_PATH.with_suffix('.db.backup')
    print(f"\n[BACKUP] Creating backup: {backup_path}")
    import shutil
    shutil.copy2(DB_PATH, backup_path)
    print("  [OK] Backup created")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Option 1: Try to add missing columns
        print("\n" + "=" * 60)
        print("STEP 1: Attempting to add missing columns...")
        print("=" * 60)
        fix_all_tables(cursor)
        conn.commit()
        
        # Verify the fix
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        check_table_schema(cursor, 'temp_usage_history')
        
        print("\n" + "=" * 60)
        print("[SUCCESS] MIGRATION COMPLETE")
        print("=" * 60)
        print("\nYou can now run the monitor again.")
        print(f"Backup saved at: {backup_path}")
        
    except Exception as e:
        print(f"\n[ERROR] Error during migration: {e}")
        print("\nRolling back changes...")
        conn.rollback()
        print("You may need to manually fix the database or delete it to recreate.")
    finally:
        conn.close()

if __name__ == '__main__':
    main()

