#!/bin/bash
set -e

echo "=== Starting deployment at $(date) ==="
echo "Current directory: $(pwd)"
echo "Files in project:"
ls -la

# Check if database already exists (to skip migration on restarts)
if [ -f "duckdb/business.db" ]; then
    echo "✅ Database already exists, skipping migration"
else
    echo "📦 Database not found, running Migration.py..."
    echo "Start time: $(date)"
    START_TIME=$(date +%s)
    python Migration.py 2>&1
    MIGRATION_EXIT=$?
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo "Migration finished at $(date), duration: $DURATION seconds"
    if [ $MIGRATION_EXIT -ne 0 ]; then
        echo "❌ Migration failed with exit code $MIGRATION_EXIT"
        exit 1
    fi
    echo "✅ Migration completed successfully"
fi

echo "=== Checking database ==="
ls -la duckdb/ || echo "duckdb directory not found"

echo "=== Starting Streamlit ==="
streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.enableXsrfProtection=falsechmod +x start.sh