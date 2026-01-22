#!/usr/bin/env python3
"""CLI tool to reset pending runs, reviews, and agentic_runs in zloth database."""

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


DEFAULT_DB_PATH = Path.home() / ".zloth" / "data" / "zloth.db"


def get_db_path(custom_path: str | None = None) -> Path:
    """Get database path."""
    if custom_path:
        return Path(custom_path)
    return DEFAULT_DB_PATH


def show_pending(conn: sqlite3.Connection) -> dict[str, int]:
    """Show counts of pending items."""
    cursor = conn.cursor()

    counts = {}

    # Pending runs
    cursor.execute("SELECT COUNT(*) FROM runs WHERE status IN ('queued', 'running')")
    counts["runs"] = cursor.fetchone()[0]

    # Pending reviews
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE status IN ('queued', 'running')")
    counts["reviews"] = cursor.fetchone()[0]

    # Active agentic_runs
    cursor.execute(
        "SELECT COUNT(*) FROM agentic_runs WHERE phase NOT IN ('completed', 'failed')"
    )
    counts["agentic_runs"] = cursor.fetchone()[0]

    return counts


def show_pending_details(conn: sqlite3.Connection) -> None:
    """Show detailed list of pending items."""
    cursor = conn.cursor()

    print("\n=== Pending Runs ===")
    cursor.execute(
        """
        SELECT id, task_id, status, executor_type, created_at
        FROM runs
        WHERE status IN ('queued', 'running')
        ORDER BY created_at DESC
        """
    )
    rows = cursor.fetchall()
    if rows:
        print(f"{'ID':<40} {'Task ID':<40} {'Status':<10} {'Executor':<15} {'Created'}")
        print("-" * 120)
        for row in rows:
            print(f"{row[0]:<40} {row[1]:<40} {row[2]:<10} {row[3]:<15} {row[4]}")
    else:
        print("No pending runs.")

    print("\n=== Pending Reviews ===")
    cursor.execute(
        """
        SELECT id, task_id, status, executor_type, created_at
        FROM reviews
        WHERE status IN ('queued', 'running')
        ORDER BY created_at DESC
        """
    )
    rows = cursor.fetchall()
    if rows:
        print(f"{'ID':<40} {'Task ID':<40} {'Status':<10} {'Executor':<15} {'Created'}")
        print("-" * 120)
        for row in rows:
            print(f"{row[0]:<40} {row[1]:<40} {row[2]:<10} {row[3]:<15} {row[4]}")
    else:
        print("No pending reviews.")

    print("\n=== Active Agentic Runs ===")
    cursor.execute(
        """
        SELECT id, task_id, phase, mode, started_at
        FROM agentic_runs
        WHERE phase NOT IN ('completed', 'failed')
        ORDER BY started_at DESC
        """
    )
    rows = cursor.fetchall()
    if rows:
        print(f"{'ID':<40} {'Task ID':<40} {'Phase':<15} {'Mode':<12} {'Started'}")
        print("-" * 120)
        for row in rows:
            print(f"{row[0]:<40} {row[1]:<40} {row[2]:<15} {row[3]:<12} {row[4]}")
    else:
        print("No active agentic runs.")


def reset_pending(
    conn: sqlite3.Connection, dry_run: bool = False, table: str | None = None
) -> dict[str, int]:
    """Reset pending items to canceled/failed status."""
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    reset_counts = {}

    tables_to_reset = []
    if table:
        tables_to_reset = [table]
    else:
        tables_to_reset = ["runs", "reviews", "agentic_runs"]

    if "runs" in tables_to_reset:
        if dry_run:
            cursor.execute(
                "SELECT COUNT(*) FROM runs WHERE status IN ('queued', 'running')"
            )
            reset_counts["runs"] = cursor.fetchone()[0]
        else:
            cursor.execute(
                """
                UPDATE runs
                SET status = 'canceled', error = 'Reset by admin', completed_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (now,),
            )
            reset_counts["runs"] = cursor.rowcount

    if "reviews" in tables_to_reset:
        if dry_run:
            cursor.execute(
                "SELECT COUNT(*) FROM reviews WHERE status IN ('queued', 'running')"
            )
            reset_counts["reviews"] = cursor.fetchone()[0]
        else:
            cursor.execute(
                """
                UPDATE reviews
                SET status = 'canceled', error = 'Reset by admin', completed_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (now,),
            )
            reset_counts["reviews"] = cursor.rowcount

    if "agentic_runs" in tables_to_reset:
        if dry_run:
            cursor.execute(
                "SELECT COUNT(*) FROM agentic_runs WHERE phase NOT IN ('completed', 'failed')"
            )
            reset_counts["agentic_runs"] = cursor.fetchone()[0]
        else:
            cursor.execute(
                """
                UPDATE agentic_runs
                SET phase = 'failed', error = 'Reset by admin'
                WHERE phase NOT IN ('completed', 'failed')
                """
            )
            reset_counts["agentic_runs"] = cursor.rowcount

    if not dry_run:
        conn.commit()

    return reset_counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset pending runs, reviews, and agentic_runs in zloth database."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be reset without making changes",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Show detailed list of pending items",
    )
    parser.add_argument(
        "--table",
        type=str,
        choices=["runs", "reviews", "agentic_runs"],
        help="Reset only specific table",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    db_path = get_db_path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)

    try:
        # Show current status
        counts = show_pending(conn)
        print(f"\nDatabase: {db_path}")
        print(f"Pending runs: {counts['runs']}")
        print(f"Pending reviews: {counts['reviews']}")
        print(f"Active agentic_runs: {counts['agentic_runs']}")

        if args.details:
            show_pending_details(conn)

        total_pending = sum(counts.values())
        if total_pending == 0:
            print("\nNo pending items to reset.")
            return

        if args.dry_run:
            print("\n[DRY RUN] Would reset:")
            reset_counts = reset_pending(conn, dry_run=True, table=args.table)
            for table_name, count in reset_counts.items():
                print(f"  - {table_name}: {count}")
            return

        # Confirmation
        if not args.yes:
            target = args.table if args.table else "all tables"
            response = input(f"\nReset pending items in {target}? [y/N]: ")
            if response.lower() != "y":
                print("Aborted.")
                return

        # Execute reset
        reset_counts = reset_pending(conn, dry_run=False, table=args.table)
        print("\nReset complete:")
        for table_name, count in reset_counts.items():
            print(f"  - {table_name}: {count} items reset")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
