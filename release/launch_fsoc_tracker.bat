@echo off
echo Starting NAYAN Optical Acquisition & Coarse Alignment...
start "" fsoc-sidecar.exe --mode simulation --port 8765
timeout /t 2 /nobreak >nul
start "" ui\index.html
