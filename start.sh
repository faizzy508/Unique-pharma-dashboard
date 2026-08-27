#!/bin/bash
set -e
echo "=== Starting Streamlit ==="
streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.enableXsrfProtection=false