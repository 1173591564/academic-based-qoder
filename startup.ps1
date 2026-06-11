# Scholar Studio — 一键启动脚本
# Usage: .\startup.ps1

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Scholar Studio — Startup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# 1. Start Docker containers
Write-Host "`n[1/3] Starting Docker containers..." -ForegroundColor Yellow
Push-Location "$ROOT\infra"
docker compose up -d
Pop-Location

# 2. Wait for healthy
Write-Host "[2/3] Waiting for services to be ready..." -ForegroundColor Yellow
$maxWait = 60
$elapsed = 0
while ($elapsed -lt $maxWait) {
    $pgOk = $false
    $neo4jOk = $false

    $pgStatus = docker inspect --format="{{.State.Health.Status}}" scholar-pg 2>$null
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
Write-Host "`n[3/3] Knowledge base status:" -ForegroundColor Yellow
$papers = docker exec scholar-pg psql -U scholar -d scholar -t -c "SELECT count(*) FROM papers;" 2>$null
$chunks = docker exec scholar-pg psql -U scholar -d scholar -t -c "SELECT count(*) FROM chunks;" 2>$null
$neo4jNodes = docker exec scholar-neo4j cypher-shell -u neo4j -p scholar2024 "MATCH (n) RETURN count(n);" 2>$null

Write-Host "  PG papers:  $($papers.Trim())"
Write-Host "  PG chunks:  $($chunks.Trim())"

Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "  Scholar Studio is ready!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Common commands:" -ForegroundColor DarkGray
Write-Host "  python -m scholar stats          # KB statistics"
Write-Host "  python -m scholar search 'query' # Full-text search"
Write-Host "  python -m scholar rag-search 'q' # Semantic search"
Write-Host "  python -m scholar bootstrap      # Full re-init"
Write-Host ""
