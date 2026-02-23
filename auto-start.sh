#!/bin/bash

echo "🚀 Auto-starting Sales Automation Servers..."

# Kill any existing servers
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "next dev" 2>/dev/null
sleep 1

# Try to detect and add common paths
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.cargo/bin:$HOME/.local/bin:$HOME/Library/Python/3.*/bin:/Applications/*/Contents/Resources/app/bin:$PATH"

# Also try to source common shell profiles
for profile in "$HOME/.zshrc" "$HOME/.zprofile" "$HOME/.bash_profile" "$HOME/.bashrc"; do
    if [ -f "$profile" ]; then
        source "$profile" 2>/dev/null
        break
    fi
done

# Navigate to backend and start it
cd /Users/gaia/Desktop/sales-automation-project-main/backend || exit 1

echo "📦 Starting Backend..."
if command -v uv &> /dev/null; then
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
    echo "✅ Backend started (PID: $!)"
else
    echo "❌ uv command not found"
    echo "PATH: $PATH"
    exit 1
fi

sleep 3

# Navigate to frontend and start it
cd /Users/gaia/Desktop/sales-automation-project-main/frontend || exit 1

echo "🎨 Starting Frontend..."
if command -v npm &> /dev/null; then
    npm run dev > /tmp/frontend.log 2>&1 &
    echo "✅ Frontend started (PID: $!)"
else
    echo "❌ npm command not found"
    echo "PATH: $PATH"
    exit 1
fi

echo ""
echo "✨ Servers are running!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo ""
echo "Check logs:"
echo "   tail -f /tmp/backend.log"
echo "   tail -f /tmp/frontend.log"
