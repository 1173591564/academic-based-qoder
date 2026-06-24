# Scholar Studio — PostToolUse Hook: Verify Citations
# After writing .tex files to output/drafts/, checks that \cite{} refs
# exist in the knowledge base (output/parsed/*.json citations field)
$ErrorActionPreference = "SilentlyContinue"

$scholarHome = $env:SCHOLAR_HOME
if (-not $scholarHome) { $scholarHome = (Get-Location).Path }

# Read stdin for tool context (file path that was written)
$context = $input | Out-String

# Try to extract file path from context
$filePath = ""
if ($context -match '"file_path"\s*:\s*"([^"]+)"') {
    $filePath = $matches[1]
}

# Only verify .tex files in output/drafts/
if (-not $filePath -or -not $filePath.EndsWith(".tex")) {
    exit 0
}

if (-not (Test-Path $filePath)) {
    exit 0
}

# Extract all \cite{key} references from the .tex file
$texContent = Get-Content $filePath -Raw -ErrorAction SilentlyContinue
if (-not $texContent) { exit 0 }

$citeKeys = [regex]::Matches($texContent, '\\cite(?:p|t|alp|author|year)?\*?\{([^}]+)\}') |
    ForEach-Object { $_.Groups[1].Value -split '[,\s]+' } |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith("%") } |
    Sort-Object -Unique

if (-not $citeKeys) { exit 0 }

# Build set of all known citation keys from parsed JSONs
$parsedDir = Join-Path $scholarHome "output\parsed"
if (-not (Test-Path $parsedDir)) { exit 0 }

$knownKeys = @{}
Get-ChildItem "$parsedDir\*.json" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $data = $_ | Get-Content -Raw | ConvertFrom-Json
        if ($data.citations) {
            foreach ($key in $data.citations) {
                $knownKeys[$key] = $true
            }
        }
    } catch {}
}

# Check each cite key
$missing = @()
foreach ($key in $citeKeys) {
    if (-not $knownKeys.ContainsKey($key)) {
        $missing += $key
    }
}

if ($missing.Count -gt 0) {
    Write-Output "[MISSING] $($missing.Count) citation(s) not found in knowledge base:"
    foreach ($key in $missing) {
        Write-Output "  - $key"
    }
    Write-Output "Consider running: python -m scholar cite-resolve --apply"
}

exit 0
