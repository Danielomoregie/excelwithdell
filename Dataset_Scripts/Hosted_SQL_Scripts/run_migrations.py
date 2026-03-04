"""
Migration Runner

Automatically runs all migration scripts in Hosted_SQL_Scripts/ in sorted order.
Safe to run multiple times - tracks applied migrations in schema_migrations table.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add parent directory to path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

MIGRATIONS_DIR = os.path.dirname(__file__)
MIGRATION_SCRIPTS = [
    'create_users_table.py',
    '002_add_password_column.py',
    # Add future migration scripts here in order
]


def run_migration(script_name):
    """Run a single migration script."""
    script_path = os.path.join(MIGRATIONS_DIR, script_name)
    
    if not os.path.exists(script_path):
        print(f"WARNING: Migration script not found: {script_name}")
        return False
    
    print(f"\n{'=' * 60}")
    print(f"Running migration: {script_name}")
    print('=' * 60)
    
    try:
        # Run the migration script as a subprocess
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=MIGRATIONS_DIR,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(f"ERROR: Migration failed with exit code {result.returncode}")
            if result.stderr:
                print("STDERR:", result.stderr)
            return False
        
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to run migration: {e}")
        return False


def main():
    print("=" * 60)
    print("  FusionTech Database Migration Runner")
    print("=" * 60)
    print(f"\nMigrations directory: {MIGRATIONS_DIR}")
    print(f"Found {len(MIGRATION_SCRIPTS)} migration(s)\n")
    
    success_count = 0
    
    for script in MIGRATION_SCRIPTS:
        if run_migration(script):
            success_count += 1
        else:
            print(f"\nMigration {script} failed. Stopping.")
            break
    
    print("\n" + "=" * 60)
    print(f"  Migration Summary: {success_count}/{len(MIGRATION_SCRIPTS)} successful")
    print("=" * 60)
    
    if success_count == len(MIGRATION_SCRIPTS):
        print("\n✓ All migrations completed successfully!")
    else:
        print("\n✗ Some migrations failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
