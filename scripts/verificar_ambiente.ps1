<#
.SYNOPSIS
    Verifica o ambiente Windows para a Central ISO.
.DESCRIPTION
    Checa cada dependência necessária e informa versões ou orientações de instalação.
#>

$ErrorActionPreference = "Continue"
$results = @()

function Check-Binary {
    param($Name, $Command, $InstallHint, $Required)
    try {
        $version = Invoke-Expression $Command 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -and $version -match '[\d\.]+') {
            $match = [regex]::Match($version, '[\d\.]+')
            $results += [PSCustomObject]@{
                Dependencia = $Name
                Versao = $match.Value
                Status = "INSTALADO"
                Observacao = ""
            }
        } else {
            throw "exit code $LASTEXITCODE"
        }
    } catch {
        $results += [PSCustomObject]@{
            Dependencia = $Name
            Versao = "—"
            Status = "AUSENTE"
            Observacao = $InstallHint
        }
    }
}

Write-Host "=== VERIFICACAO DO AMBIENTE — Central ISO ===" -ForegroundColor Cyan
Write-Host "Data: $(Get-Date -Format 'dd/MM/yyyy HH:mm')`n" -ForegroundColor Gray
Write-Host "Sistema Operacional:" -ForegroundColor Yellow
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "  $($os.Caption)  $($os.Version)  Build $($os.BuildNumber)`n"

$results += [PSCustomObject]@{ Dependencia = "Windows"; Versao = "$($os.Version) (Build $($os.BuildNumber))"; Status = "INSTALADO"; Observacao = "" }

# PowerShell version
$psVer = $PSVersionTable.PSVersion.ToString()
$results += [PSCustomObject]@{ Dependencia = "PowerShell"; Versao = $psVer; Status = "INSTALADO"; Observacao = "" }

# Git
Check-Binary -Name "Git" -Command "git --version" -InstallHint "Baixe em: https://git-scm.com/download/win"

# Node.js
Check-Binary -Name "Node.js" -Command "node --version" -InstallHint "Baixe em: https://nodejs.org/"

# npm
Check-Binary -Name "npm" -Command "npm --version" -InstallHint "Instalado com Node.js"

# Python
Check-Binary -Name "Python" -Command "py --version" -InstallHint "Baixe em: https://www.python.org/downloads/"

# pip
try {
    $pipVer = py -m pip --version 2>&1
    if ($pipVer -match 'pip ([\d\.]+)') {
        $results += [PSCustomObject]@{ Dependencia = "pip"; Versao = $matches[1]; Status = "INSTALADO"; Observacao = "" }
    }
} catch {
    $results += [PSCustomObject]@{ Dependencia = "pip"; Versao = "—"; Status = "AUSENTE"; Observacao = "python -m ensurepip --upgrade" }
}

# Rust / Cargo
Check-Binary -Name "Rust (rustc)" -Command "rustc --version" -InstallHint "Baixe em: https://rustup.rs/"
Check-Binary -Name "Cargo" -Command "cargo --version" -InstallHint "Instalado com Rust"

# Tauri CLI
Check-Binary -Name "Tauri CLI" -Command "cargo tauri --version 2>&1" -InstallHint "Execute: cargo install tauri-cli --version '^2'"

# Docker Desktop
Check-Binary -Name "Docker" -Command "docker --version" -InstallHint "Baixe em: https://www.docker.com/products/docker-desktop/"

# Docker Compose
Check-Binary -Name "Docker Compose" -Command "docker compose version" -InstallHint "Incluso no Docker Desktop"

# PostgreSQL local (opcional)
try {
    $pgVer = psql --version 2>&1
    if ($pgVer -match 'psql \(PostgreSQL\) ([\d\.]+)') {
        $results += [PSCustomObject]@{ Dependencia = "PostgreSQL (local)"; Versao = $matches[1]; Status = "INSTALADO"; Observacao = "" }
    } else { throw }
} catch {
    $results += [PSCustomObject]@{ Dependencia = "PostgreSQL (local)"; Versao = "—"; Status = "OPCIONAL"; Observacao = "Via Docker ou instalacao local" }
}

# WebView2 (necessário para Tauri)
try {
    $reg = Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -ErrorAction Stop
    $results += [PSCustomObject]@{ Dependencia = "WebView2"; Versao = $reg.pv; Status = "INSTALADO"; Observacao = "" }
} catch {
    $results += [PSCustomObject]@{ Dependencia = "WebView2"; Versao = "—"; Status = "INSTALADO (padrão Win11)"; Observacao = "Geralmente incluso no Windows 11" }
}

# Visual Studio Build Tools
try {
    $vsVer = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -property catalog_productLineVersion 2>$null
    if ($vsVer) {
        $results += [PSCustomObject]@{ Dependencia = "VS Build Tools"; Versao = $vsVer; Status = "INSTALADO"; Observacao = "" }
    } else { throw }
} catch {
    $results += [PSCustomObject]@{ Dependencia = "VS Build Tools"; Versao = "—"; Status = "OPCIONAL"; Observacao = "Necessario apenas para build Rust nativo. Baixe: https://visualstudio.microsoft.com/visual-cpp-build-tools/" }
}

# Python packages
$requiredPkgs = @("fastapi", "uvicorn", "sqlalchemy", "pydantic", "PyMuPDF", "python-docx", "openpyxl", "pytest", "alembic")
Write-Host "`nPacotes Python:" -ForegroundColor Yellow
foreach ($pkg in $requiredPkgs) {
    try {
        $ver = py -c "import $($pkg -replace '-','_'); print(getattr($($pkg -replace '-','_'), '__version__', 'instalado'))" 2>&1
        $results += [PSCustomObject]@{ Dependencia = "Python: $pkg"; Versao = $ver.Trim(); Status = "INSTALADO"; Observacao = "" }
    } catch {
        $results += [PSCustomObject]@{ Dependencia = "Python: $pkg"; Versao = "—"; Status = "AUSENTE"; Observacao = "pip install -r requirements.txt" }
    }
}

# Exibir tabela
Write-Host "`n=== TABELA DE DEPENDENCIAS ===" -ForegroundColor Cyan
$results | Format-Table -Property Dependencia, Versao, Status, Observacao -AutoSize -Wrap

Write-Host "`n=== RESUMO ===" -ForegroundColor Cyan
$ausentes = $results | Where-Object { $_.Status -eq "AUSENTE" }
$opcionais = $results | Where-Object { $_.Status -eq "OPCIONAL" }
if ($ausentes.Count -eq 0) {
    Write-Host "  Todas as dependencias obrigatorias estao instaladas." -ForegroundColor Green
} else {
    Write-Host "  $($ausentes.Count) dependencia(s) ausente(s):" -ForegroundColor Red
    $ausentes | ForEach-Object { Write-Host "    - $($_.Dependencia): $($_.Observacao)" -ForegroundColor Yellow }
}
if ($opcionais.Count -gt 0) {
    Write-Host "  $($opcionais.Count) dependencia(s) opcional(is):" -ForegroundColor Gray
    $opcionais | ForEach-Object { Write-Host "    - $($_.Dependencia): $($_.Observacao)" -ForegroundColor Gray }
}

Write-Host "`n=== PROXIMO PASSO ===" -ForegroundColor Cyan
Write-Host "  Execute: .\scripts\iniciar_central_iso.ps1" -ForegroundColor White