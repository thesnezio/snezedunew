# Run build_index.py (finds or fetches Python through app\run.ps1).
# Run:  powershell -ExecutionPolicy Bypass -File build_index.ps1   (or double-click "Rebuild index.bat")
& (Join-Path $PSScriptRoot 'app\run.ps1') 'build_index.py'
exit $LASTEXITCODE
