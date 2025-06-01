#!/usr/bin/env python3
"""
Standalone script to migrate results folder to database
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Now import with absolute imports
import database
import models
import data_migration

def main():
    print("🔄 Starting migration of results folder to database...")
    print(f"📁 Looking for log files in: {os.path.abspath('results')}")
    
    try:
        # Initialize database
        db_manager = database.get_db_manager()
        print("✅ Database initialized")
        
        # Run migration
        migrator = data_migration.DataMigrator("results")
        result = migrator.migrate_all_logs()
        
        print(f"\n🎉 Migration completed successfully!")
        print(f"📊 Sessions created: {result['sessions_created']}")
        print(f"📝 Log entries migrated: {result['logs_migrated']}")
        
        # Show some statistics
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Count sessions
            cursor.execute("SELECT COUNT(*) FROM research_sessions")
            total_sessions = cursor.fetchone()[0]
            
            # Count hypotheses
            cursor.execute("SELECT COUNT(*) FROM hypotheses")
            total_hypotheses = cursor.fetchone()[0]
            
            # Count system logs
            cursor.execute("SELECT COUNT(*) FROM system_logs")
            total_logs = cursor.fetchone()[0]
            
            print(f"\n📈 Database Statistics:")
            print(f"   Total sessions: {total_sessions}")
            print(f"   Total hypotheses: {total_hypotheses}")
            print(f"   Total log entries: {total_logs}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)