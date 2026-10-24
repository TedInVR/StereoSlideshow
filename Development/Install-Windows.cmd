@echo off
setlocal
echo Stereo Slideshow - EXPERIMENTAL WINDOWS VERSION - NOT TESTED ON WINDOWS
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0install_windows.py"
) else (
    python "%~dp0install_windows.py"
)
if errorlevel 1 echo Installation failed. Read the message above and Development\WINDOWS_README.md.
pause
