#!/bin/bash
set -e

echo "=== Pulse News App ==="
echo ""

# Backend
echo "→ Starting backend..."
cd "$(dirname "$0")/backend"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  venv/bin/pip install -q -r requirements.txt
fi
venv/bin/python app.py &
BACKEND_PID=$!
echo "  Backend running on http://localhost:5174 (PID $BACKEND_PID)"

# Frontend
echo "→ Starting frontend..."
cd "$(dirname "$0")/frontend"
if [ ! -d "node_modules" ]; then
  npm install
fi
npm run dev &
FRONTEND_PID=$!
echo "  Frontend running on http://localhost:5173 (PID $FRONTEND_PID)"

echo ""
echo "✓ Pulse is running at http://localhost:5173"
echo "  On your phone: open your phone's browser, go to your computer's IP:5173"
echo "  Then tap 'Add to Home Screen' to install as an app."
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
