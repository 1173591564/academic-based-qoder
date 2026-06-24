# Scholar Studio — One-Click Infrastructure Startup
# Starts PostgreSQL (pgvector) + Neo4j via Docker Compose
# Usage: .\scripts\start-infra.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$ProjectRoot = Split-Path $ScriptDir -Parent
$ComposeFile = Join-Path $ProjectRoot "infra\docker-compose.yml"

Write-Host "Scholar Studio — Infrastructure Startup" -ForegroundColor Cyan
Write-Host ""

# 1. Check Docker Desktop
Write-Host "[1/4] Checking Docker..." -NoNewline
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host " NOT RUNNING" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop first." -ForegroundColor Yellow
    exit 1
}
Write-Host " OK" -ForegroundColor Green

# 2. Start services
Write-Host "[2/4] Starting PostgreSQL + Neo4j..." -NoNewline
docker compose -f $ComposeFile up -d 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "  Check docker-compose.yml at $ComposeFile" -ForegroundColor Yellow
    exit 1
}
Write-Host " OK" -ForegroundColor Green

# 3. Wait for PostgreSQL
Write-Host "[3/4] Waiting for PostgreSQL..." -NoNewline
$pgReady = $false
for ($i = 0; $i -lt 30; $i++) {
    $result = docker exec scholar-postgres pg_isready -U scholar 2>&1
    if ($result -match "accepting connections") {
        $pgReady = $true
        break
    }
    Start-Sleep -Seconds 2
    Write-Host "." -NoNewline
}
if ($pgReady) {
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host " TIMEOUT" -ForegroundColor Red
}

# 4. Wait for Neo4j
Write-Host "[4/4] Waiting for Neo4j..." -NoNewline
$neo4jReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:7474" -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $neo4jReady = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 2
    Write-Host "." -NoNewline
}
if ($neo4jReady) {
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host " TIMEOUT" -ForegroundColor Red
}

# Summary
Write-Host ""
Write-Host "Infrastructure Status:" -ForegroundColor Cyan
Write-Host "  PostgreSQL:  localhost:5433  (scholar/scholar2024)" -ForegroundColor $(if ($pgReady) {'Green'} else {'Red'})
Write-Host "  Neo4j:       localhost:7474  (neo4j/scholar2024)" -ForegroundColor $(if ($neo4jReady) {'Green'} else {'Red'})
Write-Host "  Neo4j Bolt:  localhost:7687" -ForegroundColor $(if ($neo4jReady) {'Green'} else {'Red'})

if ($pgReady -and $neo4jReady) {
    Write-Host ""
    Write-Host "All services ready!" -ForegroundColor Green
}
