# Scholar Studio — 一键启动脚本
# Usage: .\startup.ps1

$ErrorActionPreference = "Stop"
$ROOT = Split-Path $PSScriptRoot -Parent

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Scholar Studio — Startup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# 0. Pre-flight checks
Write-Host "`n[0/4] Pre-flight checks..." -ForegroundColor Yellow

# Docker
$dockerOk = $false
try {
    $null = docker info 2>$null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}
if (-not $dockerOk) {
    Write-Host "  ERROR: Docker is not running or not installed." -ForegroundColor Red
    Write-Host "  Install Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
    exit 1
}
Write-Host "  Docker:       OK" -ForegroundColor Green

# Python
$pyOk = $false
try {
    $pyVer = python --version 2>$null
    if ($LASTEXITCODE -eq 0) { $pyOk = $true }
} catch {}
if (-not $pyOk) {
    Write-Host "  WARNING: Python not found. Install Python 3.10+" -ForegroundColor Red
    Write-Host "  Download: https://www.python.org/downloads/" -ForegroundColor Red
} else {
    Write-Host "  Python:       $pyVer" -ForegroundColor Green
}

# .env file
if (-not (Test-Path "$ROOT\.env")) {
    Write-Host "  .env:         NOT FOUND (copying from .env.example)" -ForegroundColor Yellow
    Copy-Item "$ROOT\.env.example" "$ROOT\.env"
    Write-Host "  .env:         Created — edit SCHOLAR_EMBEDDING_API_KEY for RAG search" -ForegroundColor Cyan
} else {
    Write-Host "  .env:         OK" -ForegroundColor Green
}

# Python dependencies
try {
    $null = python -c "import typer" 2>$null
    if ($LASTEXITCODE -ne 0) { throw }
    Write-Host "  Dependencies: OK" -ForegroundColor Green
} catch {
    Write-Host "  Dependencies: MISSING — run: python -m pip install ." -ForegroundColor Yellow
}

# 1. Start Docker containers
Write-Host "`n[1/4] Starting Docker containers..." -ForegroundColor Yellow
Push-Location "$ROOT\infra\scholar"
docker compose up -d
Pop-Location

# 2. Wait for healthy
Write-Host "[2/4] Waiting for services to be ready..." -ForegroundColor Yellow
$maxWait = 60
$elapsed = 0
while ($elapsed -lt $maxWait) {
    $pgOk = $false
    $neo4jOk = $false

    $pgStatus = docker inspect --format="{{.State.Health.Status}}" scholar-postgres 2>$null
    if ($pgStatus -eq "healthy") { $pgOk = $true }

    $neo4jStatus = docker inspect --format="{{.State.Health.Status}}" scholar-neo4j 2>$null
    if ($neo4jStatus -eq "healthy") { $neo4jOk = $true }

    if ($pgOk -and $neo4jOk) {
        Write-Host "  PostgreSQL (5433): OK" -ForegroundColor Green
        Write-Host "  Neo4j     (7474): OK" -ForegroundColor Green
        break
    }

    Start-Sleep -Seconds 3
    $elapsed += 3
    Write-Host "  Waiting... ($elapsed s)" -ForegroundColor DarkGray
}

if ($elapsed -ge $maxWait) {
    Write-Host "  WARNING: Timed out waiting for services" -ForegroundColor Red
}

# 3. Quick status check
Write-Host "`n[3/4] Knowledge base status:" -ForegroundColor Yellow
$papers = docker exec scholar-postgres psql -U scholar -d scholar -t -c "SELECT count(*) FROM papers;" 2>$null
$chunks = docker exec scholar-postgres psql -U scholar -d scholar -t -c "SELECT count(*) FROM chunks;" 2>$null
$neo4jNodes = docker exec scholar-neo4j cypher-shell -u neo4j -p scholar2024 "MATCH (n) RETURN count(n);" 2>$null

Write-Host "  PG papers:  $($papers.Trim())"
Write-Host "  PG chunks:  $($chunks.Trim())"

Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "  Scholar Studio is ready!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan

# 4. Next steps
Write-Host "`n[4/4] Next steps:" -ForegroundColor Yellow
$papersCount = 0
if ($papers) { $papersCount = [int](($papers | Where-Object { $_.Trim() -ne '' } | Select-Object -Last 1).Trim()) }
if ($papersCount -eq 0) {
    Write-Host "  Knowledge base is empty. Run bootstrap to initialize:" -ForegroundColor Cyan
    Write-Host "    python -m scholar bootstrap      # Full init (~40 min)" -ForegroundColor White
} else {
    Write-Host "  $papersCount papers loaded. You can start working:" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "Phase 2 — Workspace initialization:" -ForegroundColor Yellow
Write-Host "  To start working in a project directory:" -ForegroundColor Cyan
Write-Host "    cd <your-project>" -ForegroundColor White
Write-Host "    scholar init-workspace" -ForegroundColor White
Write-Host ""
Write-Host "Common commands:" -ForegroundColor DarkGray
Write-Host "  scholar stats              # KB statistics"
Write-Host "  scholar search 'query'     # Full-text search"
Write-Host "  scholar kb-update --query 'topic' --max 5  # Add new papers"
Write-Host ""
Write-Host "In Qoder IDE, just type naturally:" -ForegroundColor DarkGray
Write-Host "  调研 Transformer / 精读 2401.04088 / 维护知识库" -ForegroundColor White
Write-Host ""
