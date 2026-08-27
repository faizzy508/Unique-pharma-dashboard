#!/bin/bash
set -e

echo "=== Starting deployment at $(date) ==="
echo "Current directory: $(pwd)"

# Check if database already exists
if [ -f "duckdb/business.db" ]; then
    echo "✅ Database already exists, skipping creation"
else
    echo "📦 Database not found, creating sample data..."
    python create_sample_db.py
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create sample database"
        exit 1
    fi
    echo "✅ Sample database created"
fi

echo "=== Starting Streamlit ==="
streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.enableXsrfProtection=false