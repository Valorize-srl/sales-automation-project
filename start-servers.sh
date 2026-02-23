#!/bin/bash

echo "🚀 Starting Sales Automation Servers..."

# Kill any existing servers
pkill -f "uvicorn app.main:app"
pkill -f "next dev"

# Start backend
echo "📦 Starting Backend..."
cd /Users/gaia/Desktop/sales-automation-project-main/backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"

# Wait for backend to start
sleep 3

# Start frontend
echo "🎨 Starting Frontend..."
cd /Users/gaia/Desktop/sales-automation-project-main/frontend
npm run dev &
FRONTEND_PID=$!
echo "✅ Frontend started (PID: $FRONTEND_PID)"

echo ""
echo "✨ Servers are running!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for user interrupt
trap "echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
