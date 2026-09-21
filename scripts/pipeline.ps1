param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'start', 'configure', 'generate', 'validate', 'run', 'report', 'explain', 'demo', 'test', 'check', 'serve', 'logs', 'stop')]
    [string]$Action = 'start',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PipelineArguments = @()
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$composePath = Join-Path $projectRoot 'compose.yaml'

function Invoke-Compose {
    param([string[]]$ComposeArguments)
    & docker compose --project-directory $projectRoot --file $composePath @ComposeArguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

switch ($Action) {
    'setup' {
        if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) {
            Copy-Item -LiteralPath (Join-Path $projectRoot '.env.example') -Destination (Join-Path $projectRoot '.env')
        }
        Invoke-Compose -ComposeArguments @('build', 'pipeline')
        Invoke-Compose -ComposeArguments @('run', '--rm', '--entrypoint', 'python', 'pipeline', '-m', 'pytest', 'tests/integration/test_smoke.py', '-q')
    }
    'start' { Invoke-Compose -ComposeArguments @('run', '--rm', 'pipeline', '--help') }
    'test' { Invoke-Compose -ComposeArguments (@('run', '--rm', '--entrypoint', 'python', 'pipeline', '-m', 'pytest') + $PipelineArguments) }
    'check' {
        Invoke-Compose -ComposeArguments @('run', '--rm', '--entrypoint', 'sh', 'pipeline', '-c', 'ruff check src tests scripts && ruff format --check src tests scripts && mypy src/retail_pipeline')
    }
    'serve' { Invoke-Compose -ComposeArguments @('--profile', 'report', 'up', '-d', 'report-server') }
    'logs' { Invoke-Compose -ComposeArguments @('run', '--rm', '--entrypoint', 'python', 'pipeline', 'scripts/show_logs.py') }
    'stop' { Invoke-Compose -ComposeArguments @('--profile', 'report', 'down') }
    default { Invoke-Compose -ComposeArguments (@('run', '--rm', 'pipeline', $Action) + $PipelineArguments) }
}
