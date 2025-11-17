#!/usr/bin/env python3
"""
Test Oracle Database Connection
Quick script to verify database connectivity before running monitor
"""

import json
import sys
import oracledb

def test_connection(config_path='config.json'):
    """Test database connection"""
    try:
        # Load configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        db_config = config['database']
        
        print(f"Testing connection to {db_config['host']}:{db_config['port']}/{db_config['service_name']}")
        print(f"Username: {db_config['username']}")
        print("Connecting...")
        
        # Create DSN
        dsn = oracledb.makedsn(
            db_config['host'],
            db_config['port'],
            service_name=db_config['service_name']
        )
        
        # Connect
        connection = oracledb.connect(
            user=db_config['username'],
            password=db_config['password'],
            dsn=dsn
        )
        
        # Test query
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM v$session WHERE username IS NOT NULL")
        session_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT version FROM v$instance")
        version = cursor.fetchone()[0]
        
        cursor.close()
        connection.close()
        
        print("✓ Connection successful!")
        print(f"✓ Oracle Version: {version}")
        print(f"✓ Current Sessions: {session_count}")
        print("\nConnection test passed. You can now run oracle_monitor.py")
        return True
        
    except FileNotFoundError:
        print(f"ERROR: Configuration file {config_path} not found")
        print("Please copy config.example.json to config.json and configure it")
        return False
    except oracledb.Error as e:
        print(f"ERROR: Database connection failed: {e}")
        print("\nPlease check:")
        print("1. Database host, port, and service name")
        print("2. Username and password")
        print("3. Network connectivity")
        print("4. Oracle listener is running")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return False

if __name__ == '__main__':
    config_file = sys.argv[1] if len(sys.argv) > 1 else 'config.json'
    success = test_connection(config_file)
    sys.exit(0 if success else 1)

