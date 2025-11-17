#!/usr/bin/env python3
"""
Aggregate Oracle monitor session logs to find top CPU/memory consumers.

Usage:
    python tools/analyze_sessions.py [--log-file logs/sessions.jsonl] [--top 10]
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Tuple


def load_sessions(log_path: Path) -> Dict[Tuple[int, str], Dict]:
    agg = defaultdict(lambda: {
        'cpu': 0.0,
        'mem': 0.0,
        'count': 0,
        'sql_text': '',
        'sql_text_full': '',
        'username': '',
        'program': '',
        'module': '',
        'session_type': ''
    })

    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    with log_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            session_type = entry.get('session_type')
            sessions = entry.get('sessions')
            if not isinstance(sessions, list):
                data = entry.get('data')
                if data:
                    sessions = [data]
                else:
                    continue

            for sess in sessions:
                sid = sess.get('SID')
                sql_id = sess.get('SQL ID') or sess.get('sql_id')
                key = (sid, sql_id)
                agg[key]['cpu'] += float(sess.get('CPU (seconds)', sess.get('cpu_seconds', 0)) or 0)
                agg[key]['mem'] += float(sess.get('PGA (MB)', sess.get('pga_mb', 0)) or 0)
                agg[key]['count'] += 1

                full_text = sess.get('SQL Text Full') or sess.get('sql_text_full') or \
                            sess.get('SQL Text') or sess.get('sql_text') or ''
                preview_text = sess.get('SQL Text') or sess.get('sql_text') or ''

                if full_text and not agg[key]['sql_text_full']:
                    agg[key]['sql_text_full'] = full_text
                if preview_text and not agg[key]['sql_text']:
                    agg[key]['sql_text'] = preview_text
                elif full_text and not agg[key]['sql_text']:
                    agg[key]['sql_text'] = full_text[:500]

                agg[key]['username'] = sess.get('Username') or sess.get('username') or agg[key]['username']
                agg[key]['program'] = sess.get('Program') or sess.get('program') or agg[key]['program']
                agg[key]['module'] = sess.get('Module') or sess.get('module') or agg[key]['module']
                agg[key]['session_type'] = session_type or agg[key]['session_type']

    return agg


def print_top(agg: Dict, top_n: int, full_sql: bool = False) -> None:
    top_cpu = sorted(agg.items(), key=lambda kv: kv[1]['cpu'], reverse=True)[:top_n]
    print("Top sessions by cumulative CPU seconds:")
    for (sid, sql_id), stats in top_cpu:
        print(f"SID={sid} SQL_ID={sql_id} CPU={stats['cpu']:.2f}s samples={stats['count']} "
              f"user={stats['username']} program={stats['program']}")
        sql_blob = stats['sql_text_full'] if full_sql else stats['sql_text']
        if sql_blob:
            text = sql_blob.replace('\n', ' ') if full_sql else sql_blob.replace('\n', ' ')[:200]
            print(f"  SQL: {text}")

    print("\nTop sessions by cumulative PGA MB:")
    top_mem = sorted(agg.items(), key=lambda kv: kv[1]['mem'], reverse=True)[:top_n]
    for (sid, sql_id), stats in top_mem:
        print(f"SID={sid} SQL_ID={sql_id} PGA={stats['mem']:.2f}MB samples={stats['count']} "
              f"user={stats['username']} program={stats['program']}")
        sql_blob = stats['sql_text_full'] if full_sql else stats['sql_text']
        if sql_blob:
            text = sql_blob.replace('\n', ' ') if full_sql else sql_blob.replace('\n', ' ')[:200]
            print(f"  SQL: {text}")


def group_entries(
    agg: Dict,
    group_mode: str,
    top_n: int,
    full_sql: bool = False
) -> None:
    if group_mode not in {'user', 'program', 'sql', 'user_program', 'module'}:
        return

    grouped = defaultdict(lambda: {
        'session_count': 0,
        'total_cpu': 0.0,
        'total_pga': 0.0,
        'username': '',
        'program': '',
        'module': '',
        'sample_sql_id': '',
        'sample_sql_text': ''
    })

    for (sid, sql_id), stats in agg.items():
        username = stats.get('username') or 'N/A'
        program = stats.get('program') or 'N/A'
        module = stats.get('module') or 'N/A'
        sql_key = sql_id or 'N/A'

        if group_mode == 'user':
            key = username
        elif group_mode == 'program':
            key = program
        elif group_mode == 'sql':
            key = sql_key
        elif group_mode == 'module':
            key = module
        else:  # user_program
            key = f"{username} | {program}"

        entry = grouped[key]
        entry['session_count'] += stats['count']
        entry['total_cpu'] += stats['cpu']
        entry['total_pga'] += stats['mem']
        entry['username'] = username
        entry['program'] = program
        entry['module'] = module
        if stats.get('sql_text_full') and not entry['sample_sql_text']:
            entry['sample_sql_text'] = stats['sql_text_full']
            entry['sample_sql_id'] = sql_key
        elif stats.get('sql_text') and not entry['sample_sql_text']:
            entry['sample_sql_text'] = stats['sql_text']
            entry['sample_sql_id'] = sql_key

    if not grouped:
        print("No groups available.")
        return

    sorted_groups = sorted(
        grouped.items(),
        key=lambda kv: (kv[1]['session_count'], kv[1]['total_cpu']),
        reverse=True
    )[:top_n]

    print(f"\nTop groups by '{group_mode}':")
    for key, stats in sorted_groups:
        print(
            f"{key} -> sessions={stats['session_count']} "
            f"CPU={stats['total_cpu']:.2f}s PGA={stats['total_pga']:.2f}MB"
        )
        sql_blob = stats['sample_sql_text']
        if sql_blob:
            text = sql_blob if full_sql else sql_blob.replace('\n', ' ')[:200]
            print(f"  SQL[{stats.get('sample_sql_id','N/A')}]: {text}")


def main():
    parser = argparse.ArgumentParser(description="Analyze Oracle session logs for resource usage.")
    parser.add_argument('--log-file', default='logs/sessions.jsonl', help='Path to sessions log file')
    parser.add_argument('--top', type=int, default=10, help='Number of entries to display per metric')
    parser.add_argument('--full-sql', action='store_true', help='Print complete SQL text instead of preview')
    parser.add_argument(
        '--group-by',
        choices=['none', 'user', 'program', 'sql', 'user_program', 'module'],
        default='none',
        help='Aggregate sessions by attribute to spot short-job swarms'
    )
    args = parser.parse_args()

    agg = load_sessions(Path(args.log_file))
    if not agg:
        print("No session entries found.")
        return

    print_top(agg, args.top, full_sql=args.full_sql)
    if args.group_by != 'none':
        group_entries(agg, args.group_by, args.top, full_sql=args.full_sql)


if __name__ == '__main__':
    main()

