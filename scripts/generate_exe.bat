@echo off
cd /d "%~dp0.."
"venv\Scripts\python.exe" "scripts\build_desktop.py"
if errorlevel 1 (
    echo Build failed. See build\exe-build.log
    exit /b 1
)
echo Build complete: dist\MahjongCopilotPlus\MahjongCopilotPlus.exe
