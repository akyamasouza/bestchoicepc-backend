param(
    [string]$EntityType = "all",
    [int]$Limit = 1,
    [string]$Channel = ""
)

Set-Location $PSScriptRoot\..\..

$command = @(
    "python",
    "-m",
    "app.scripts.run_catalog_candidate_pipeline",
    "--entity-type",
    $EntityType,
    "--limit",
    $Limit
)

if ($Channel -ne "") {
    $command += @("--channel", $Channel)
}

& $command[0] $command[1..($command.Length - 1)]
exit $LASTEXITCODE
