cat > start.sh << 'EOF'
#!/bin/bash
python Migration.py
streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.enableXsrfProtection=false
EOF