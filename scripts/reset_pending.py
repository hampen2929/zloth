#!/usr/bin/env python3
"""Reset pending items in zloth database.

This CLI tool resets stuck or pending items in the zloth SQLite database.
It handles the following tables:
  - runs: Pending runs (status: queued, running) → canceled
  - reviews: Pending reviews (status: queued, running) → canceled
  - agentic_runs: Active agentic runs (phase: not completed/failed) → failed
  - ci_checks: Pending CI checks (status: pending) → deleted

Usage:
    # Show current pending counts (dry-run)
    python scripts/reset_pending.py --dry-run

    # Show detailed list of pending items
    python scripts/reset_pending.py --details

    # Show breakdown by task (which tasks have pending items)
    python scripts/reset_pending.py --breakdown

    # Reset all pending items (with confirmation)
    python scripts/reset_pending.py

    # Reset all pending items (skip confirmation)
    python scripts/reset_pending.py -y

    # Reset only specific table
    python scripts/reset_pending.py --table ci_checks -y
    python scripts/reset_pending.py --table runs -y

    # Use custom database path
    python scripts/reset_pending.py --db /path/to/zloth.db -y

Examples:
    # Check what would be reset without making changes
    $ python scripts/reset_pending.py --dry-run
    Database: /home/user/.zloth/data/zloth.db
    Pending runs: 5
    Pending reviews: 0
    Active agentic_runs: 0
    Pending ci_checks: 490

    [DRY RUN] Would reset:
      - runs: 5
      - reviews: 0
      - agentic_runs: 0
      - ci_checks: 490

    # Reset only CI checks
    $ python scripts/reset_pending.py --table ci_checks -y
    Database: /home/user/.zloth/data/zloth.db
    Pending runs: 5
    Pending reviews: 0
    Active agentic_runs: 0
    Pending ci_checks: 490

    Reset complete:
      - ci_checks: 490 items reset

    # Show breakdown by task
    $ python scripts/reset_pending.py --breakdown
    Database: /home/user/.zloth/data/zloth.db

    === Pending Items by Task ===
    Task: Fix login bug (abc123...)
      - runs: 2
      - ci_checks: 10

    Task: Add feature X (def456...)
      - ci_checks: 5
"""

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


DEFAULT_DB_PATH = Path.home() / ".zloth" / "data" / "zloth.db"


def get_db_path(custom_path: str | None = None) -> Path:
    """Get database path.

    Args:
        custom_path: Optional custom database path.

    Returns:
        Path to the database file.
    """
    if custom_path:
        return Path(custom_path)
    return DEFAULT_DB_PATH


def show_pending(conn: sqlite3.Connection) -> dict[str, int]:
    """Get counts of pending items in each table.

    Args:
        conn: SQLite database connection.

    Returns:
        Dictionary mapping table names to pending item counts.
    """
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

    # Pending ci_checks
    cursor.execute("SELECT COUNT(*) FROM ci_checks WHERE status = 'pending'")
    counts["ci_checks"] = cursor.fetchone()[0]

    return counts


def show_pending_details(conn: sqlite3.Connection) -> None:
    """Print detailed list of pending items.

    Args:
        conn: SQLite database connection.
    """
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

    print("\n=== Pending CI Checks ===")
    cursor.execute(
        """
        SELECT id, task_id, pr_id, status, created_at
        FROM ci_checks
        WHERE status = 'pending'
        ORDER BY created_at DESC
        LIMIT 20
        """
    )
    rows = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM ci_checks WHERE status = 'pending'")
    total = cursor.fetchone()[0]
    if rows:
        print(f"{'ID':<40} {'Task ID':<40} {'PR ID':<40} {'Status':<10} {'Created'}")
        print("-" * 150)
        for row in rows:
            print(f"{row[0]:<40} {row[1]:<40} {row[2]:<40} {row[3]:<10} {row[4]}")
        if total > 20:
            print(f"... and {total - 20} more")
    else:
        print("No pending CI checks.")


def show_pending_breakdown(conn: sqlite3.Connection) -> None:
    """Print pending items grouped by task.

    Args:
        conn: SQLite database connection.
    """
    cursor = conn.cursor()

    # Get all tasks with pending items
    cursor.execute(
        """
        SELECT
            t.id,
            t.title,
            t.created_at,
            COALESCE(r.run_count, 0) as pending_runs,
            COALESCE(rv.review_count, 0) as pending_reviews,
            COALESCE(ar.agentic_count, 0) as active_agentic_runs,
            COALESCE(ci.ci_count, 0) as pending_ci_checks
        FROM tasks t
        LEFT JOIN (
            SELECT task_id, COUNT(*) as run_count
            FROM runs
            WHERE status IN ('queued', 'running')
            GROUP BY task_id
        ) r ON t.id = r.task_id
        LEFT JOIN (
            SELECT task_id, COUNT(*) as review_count
            FROM reviews
            WHERE status IN ('queued', 'running')
            GROUP BY task_id
        ) rv ON t.id = rv.task_id
        LEFT JOIN (
            SELECT task_id, COUNT(*) as agentic_count
            FROM agentic_runs
            WHERE phase NOT IN ('completed', 'failed')
            GROUP BY task_id
        ) ar ON t.id = ar.task_id
        LEFT JOIN (
            SELECT task_id, COUNT(*) as ci_count
            FROM ci_checks
            WHERE status = 'pending'
            GROUP BY task_id
        ) ci ON t.id = ci.task_id
        WHERE COALESCE(r.run_count, 0) > 0
           OR COALESCE(rv.review_count, 0) > 0
           OR COALESCE(ar.agentic_count, 0) > 0
           OR COALESCE(ci.ci_count, 0) > 0
        ORDER BY
            COALESCE(ci.ci_count, 0) DESC,
            COALESCE(r.run_count, 0) DESC,
            t.created_at DESC
        """
    )
    rows = cursor.fetchall()

    if not rows:
        print("\n=== Pending Items by Task ===")
        print("No tasks with pending items.")
        return

    print("\n=== Pending Items by Task ===")
    print(f"Found {len(rows)} task(s) with pending items:\n")

    total_runs = 0
    total_reviews = 0
    total_agentic = 0
    total_ci = 0

    for row in rows:
        task_id, title, created_at, runs, reviews, agentic, ci = row
        short_id = task_id[:8] + "..."
        display_title = title[:50] + "..." if len(title) > 50 else title

        print(f"Task: {display_title} ({short_id})")
        print(f"  Created: {created_at}")

        items = []
        if runs > 0:
            items.append(f"runs: {runs}")
            total_runs += runs
        if reviews > 0:
            items.append(f"reviews: {reviews}")
            total_reviews += reviews
        if agentic > 0:
            items.append(f"agentic_runs: {agentic}")
            total_agentic += agentic
        if ci > 0:
            items.append(f"ci_checks: {ci}")
            total_ci += ci

        for item in items:
            print(f"    - {item}")
        print()

    print("-" * 60)
    print("Summary:")
    print(f"  Total tasks with pending items: {len(rows)}")
    if total_runs > 0:
        print(f"  Total pending runs: {total_runs}")
    if total_reviews > 0:
        print(f"  Total pending reviews: {total_reviews}")
    if total_agentic > 0:
        print(f"  Total active agentic_runs: {total_agentic}")
    if total_ci > 0:
        print(f"  Total pending ci_checks: {total_ci}")


def reset_pending(
    conn: sqlite3.Connection, dry_run: bool = False, table: str | None = None
) -> dict[str, int]:
    """Reset pending items to canceled/failed status.

    Args:
        conn: SQLite database connection.
        dry_run: If True, only return counts without making changes.
        table: If specified, only reset items in this table.

    Returns:
        Dictionary mapping table names to number of items reset.
    """
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    reset_counts = {}

    tables_to_reset = []
    if table:
        tables_to_reset = [table]
    else:
        tables_to_reset = ["runs", "reviews", "agentic_runs", "ci_checks"]

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

    if "ci_checks" in tables_to_reset:
        if dry_run:
            cursor.execute("SELECT COUNT(*) FROM ci_checks WHERE status = 'pending'")
            reset_counts["ci_checks"] = cursor.fetchone()[0]
        else:
            cursor.execute(
                """
                DELETE FROM ci_checks WHERE status = 'pending'
                """
            )
            reset_counts["ci_checks"] = cursor.rowcount

    if not dry_run:
        conn.commit()

    return reset_counts


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Reset pending runs, reviews, agentic_runs, and ci_checks in zloth database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run              Show pending counts without making changes
  %(prog)s --details              Show detailed list of pending items
  %(prog)s --breakdown            Show pending items grouped by task
  %(prog)s -y                     Reset all pending items (skip confirmation)
  %(prog)s --table ci_checks -y   Reset only pending CI checks
  %(prog)s --table runs -y        Reset only pending runs
        """,
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
        "--breakdown",
        action="store_true",
        help="Show pending items grouped by task",
    )
    parser.add_argument(
        "--table",
        type=str,
        choices=["runs", "reviews", "agentic_runs", "ci_checks"],
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
        print(f"Pending ci_checks: {counts['ci_checks']}")

        if args.details:
            show_pending_details(conn)

        if args.breakdown:
            show_pending_breakdown(conn)

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
