# Builds dist\CheatDock\ (CheatDock.exe + editable config and cheat sheets)
# and dist\CheatDock-windows.zip.
# Usage:  .\build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = if (Test-Path .\.venv\Scripts\python.exe) { ".\.venv\Scripts\python.exe" } else { "python" }
& $py -m pip install --quiet -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Remove-Item .\build, .\dist -Recurse -Force -ErrorAction SilentlyContinue
& $py -m PyInstaller --noconfirm --onefile --windowed --name CheatDock `
    --distpath .\dist\CheatDock run_cheatdock.pyw
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Copy-Item .\config.yaml .\dist\CheatDock\
Copy-Item .\cheatsheets .\dist\CheatDock\cheatsheets -Recurse
Compress-Archive -Path .\dist\CheatDock\* -DestinationPath .\dist\CheatDock-windows.zip -Force

Write-Host "Done: dist\CheatDock\CheatDock.exe and dist\CheatDock-windows.zip" -ForegroundColor Green
