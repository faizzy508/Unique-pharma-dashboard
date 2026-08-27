#!/bin/bash
set -e
echo "=== Starting deployment ==="
echo "Current directory: $(pwd)"
echo "Files in project:"
ls -la

echo "=== Running Migration.py ==="
python Migration.py
if [ $? -ne 0 ]; then
    echo "❌ Migration.py failed!"
    exit 1
fi

echo "=== Migration succeeded, starting Streamlit ==="
streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.enableXsrfProtection=falsechmod +x start.sh