#!/bin/bash
# VANL Quick Deploy Script
# Run this to deploy VANL to Render.com for free

set -e

echo "🚀 VANL Quick Deploy Script"
echo "============================"
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📦 Initializing Git repository..."
    git init
    git add .
    git commit -m "Initial VANL deployment"
    git branch -M main
    echo "✅ Git initialized"
else
    echo "✅ Git repository already exists"
fi

# Check if remote exists
if ! git remote | grep -q "origin"; then
    echo ""
    echo "⚠️  No GitHub remote found"
    echo "Please create a GitHub repository and run:"
    echo "  git remote add origin https://github.com/YOUR_USERNAME/vanl.git"
    echo "  git push -u origin main"
    echo ""
    echo "Then go to https://render.com and:"
    echo "  1. Sign up with GitHub"
    echo "  2. Click 'New +' → 'Web Service'"
    echo "  3. Connect your repository"
    echo "  4. Render will auto-detect render.yaml"
    echo "  5. Click 'Create Web Service'"
    echo ""
    echo "Your API will be live at: https://vanl-api.onrender.com"
else
    echo "✅ GitHub remote configured"
    echo ""
    echo "📤 Pushing to GitHub..."
    git push -u origin main
    echo "✅ Code pushed to GitHub"
    echo ""
    echo "🌐 Next steps:"
    echo "  1. Go to https://render.com"
    echo "  2. Sign up with GitHub"
    echo "  3. Click 'New +' → 'Web Service'"
    echo "  4. Connect your repository"
    echo "  5. Render will auto-detect render.yaml"
    echo "  6. Click 'Create Web Service'"
    echo ""
    echo "Your API will be live in ~5 minutes at:"
    echo "  https://vanl-api.onrender.com"
    echo "  https://vanl-api.onrender.com/docs"
fi

echo ""
echo "✨ Deployment preparation complete!"
