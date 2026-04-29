@echo off
REM VANL Quick Deploy Script for Windows
echo.
echo ========================================
echo   VANL Quick Deploy
echo ========================================
echo.

REM Check if git is initialized
if not exist ".git" (
    echo [1/3] Initializing Git repository...
    git init
    git add .
    git commit -m "Deploy VANL"
    git branch -M main
    echo Done!
) else (
    echo [1/3] Git repository already exists
)

echo.
echo [2/3] Next steps:
echo.
echo 1. Create a repository on GitHub.com
echo 2. Run this command:
echo    git remote add origin https://github.com/YOUR_USERNAME/vanl.git
echo    git push -u origin main
echo.
echo 3. Go to https://render.com
echo    - Sign up with GitHub
echo    - Click "New +" -^> "Web Service"
echo    - Select your repository
echo    - Click "Create Web Service"
echo.
echo [3/3] Your API will be live at:
echo    https://vanl-api.onrender.com
echo    https://vanl-api.onrender.com/docs
echo.
echo Share RESEARCHER_GUIDE.md with your team!
echo.
pause
