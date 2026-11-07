param([string]$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe")
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$version = python -c "from quickbox.version import VERSION; print(VERSION)"
if ($LASTEXITCODE -ne 0) { throw 'Unable to read version' }
python -m PyInstaller --noconfirm --clean --windowed --name QuickBox launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
if (-not (Test-Path -LiteralPath $Iscc)) { throw "Inno Setup compiler not found: $Iscc" }
& $Iscc "/DMyAppVersion=$version" 'installer\quickbox.iss'
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }
