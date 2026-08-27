#!/bin/bash
set -e

echo "=== Starting deployment at $(date) ==="
echo "Current directory: $(pwd)"

# Ensure the duckdb directory exists
mkdir -p duckdb

# Run the real migration
echo "📦 Running migration with real data..."
START_TIME=$(date +%s)
python Migration.py
MIGRATION_EXIT=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo "Migration took $DURATION seconds."

if [ $MIGRATION_EXIT -ne 0 ]; then
    echo "❌ Migration failed with exit code $MIGRATION_EXIT"
    exit 1
fi

echo "✅ Migration completed successfully"

# Start the app
echo "=== Starting Streamlit ==="
streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.enableXsrfProtection=false