#!/bin/bash
cd /Users/Danie/Documents/crosslist-eu
export PYTHONPATH=/Users/Danie/Documents/crosslist-eu

# Kill any existing instance on port 8001
lsof -ti:8001 | xargs kill -9 2>/dev/null

echo "CrossList EU backend starten op http://localhost:8001 ..."
exec /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
  -m uvicorn backend.main:app --port 8001 --log-level info
