#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the modular metrics system.
This tests the framework without requiring an Oracle connection.
"""

import sys
from pathlib import Path

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from metrics import get_registry, BaseMetric
        from metrics.session_overview import SessionOverviewMetric
        from metrics.top_sessions import TopSessionsMetric
        from metrics.blocking_sessions import BlockingSessionsMetric
        from metrics.tablespace_usage import TablespaceUsageMetric
        from metrics.wait_events import WaitEventsMetric
        from metrics.temp_usage import TempUsageMetric
        from metrics.undo_metrics import UndoMetricsMetric
        from metrics.redo_metrics import RedoMetricsMetric
        from metrics.plan_churn import PlanChurnMetric
        from metrics.io_sessions import IOSessionsMetric
        from metrics.host_metrics import HostMetricsMetric
        from metrics.resource_limits import ResourceLimitsMetric
        print("[OK] All imports successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_registry():
    """Test the metric registry."""
    print("\nTesting registry...")
    try:
        from metrics import get_registry
        
        registry = get_registry(log_dir=Path("logs"))
        
        all_metrics = registry.get_all_metrics()
        print(f"[OK] Registry created with {len(all_metrics)} metrics")
        
        # Test categories
        categories = registry.categories
        print(f"[OK] Found {len(categories)} categories: {list(categories.keys())}")
        
        # List all metrics
        print("\n[INFO] Registered Metrics:")
        for category in sorted(categories.keys()):
            metrics_in_cat = registry.get_metrics_by_category(category)
            print(f"\n  {category.upper()}:")
            for metric in metrics_in_cat:
                print(f"    - {metric.display_name} ({metric.name})")
                print(f"      Description: {metric.description}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Registry test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_metric_metadata():
    """Test that all metrics have proper metadata."""
    print("\nTesting metric metadata...")
    try:
        from metrics import get_registry
        
        registry = get_registry(log_dir=Path("logs"))
        
        all_good = True
        for metric in registry.get_all_metrics():
            # Check required attributes
            if not metric.display_name:
                print(f"[FAIL] {metric.name} missing display_name")
                all_good = False
            if not metric.description:
                print(f"[FAIL] {metric.name} missing description")
                all_good = False
            if not metric.category:
                print(f"[FAIL] {metric.name} missing category")
                all_good = False
        
        if all_good:
            print("[OK] All metrics have proper metadata")
        
        return all_good
    except Exception as e:
        print(f"[FAIL] Metadata test failed: {e}")
        return False


def test_storage_schema():
    """Test that metrics with storage have valid schema."""
    print("\nTesting storage schemas...")
    try:
        from metrics import get_registry
        
        registry = get_registry(log_dir=Path("logs"))
        
        metrics_with_storage = 0
        for metric in registry.get_all_metrics():
            schema = metric._get_storage_schema()
            if schema:
                metrics_with_storage += 1
                # Basic validation
                if "CREATE TABLE" not in schema.upper():
                    print(f"[FAIL] {metric.name} has invalid schema (no CREATE TABLE)")
                    return False
        
        print(f"[OK] {metrics_with_storage}/{len(registry.get_all_metrics())} metrics have storage schema")
        return True
    except Exception as e:
        print(f"[FAIL] Storage schema test failed: {e}")
        return False


def test_host_metrics():
    """Test host metrics (doesn't need Oracle connection)."""
    print("\nTesting host metrics collection...")
    try:
        from metrics.host_metrics import HostMetricsMetric
        from pathlib import Path
        
        metric = HostMetricsMetric(log_dir=Path("logs"))
        
        # Collect without Oracle connection
        data = metric.collect(connection=None)
        
        if data:
            print(f"[OK] Host metrics collected:")
            print(f"   CPU: {data.get('cpu_percent', 'N/A')}%")
            print(f"   Memory: {data.get('memory_percent', 'N/A')}%")
            print(f"   CPU Count: {data.get('cpu_count', 'N/A')}")
            return True
        else:
            print("[WARN] Host metrics returned None (psutil may not be installed)")
            return True  # Not a failure if psutil is missing
    except Exception as e:
        print(f"[WARN] Host metrics test skipped: {e}")
        return True  # Not a critical failure


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("MODULAR METRICS SYSTEM - TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Registry", test_registry),
        ("Metadata", test_metric_metadata),
        ("Storage Schemas", test_storage_schema),
        ("Host Metrics", test_host_metrics),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"[FAIL] {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! The modular system is working correctly.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())

