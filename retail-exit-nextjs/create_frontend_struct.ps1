$BaseDir = "c:\Users\DELL\.gemini\antigravity\scratch\N\retail-exit-nextjs\src"

$Dirs = @(
    "app\(dashboard)",
    "app\(dashboard)\events",
    "app\(dashboard)\events\[eventId]",
    "app\(dashboard)\alerts",
    "app\(dashboard)\products",
    "app\(dashboard)\employees",
    "app\(dashboard)\employees\[employeeId]",
    "app\(dashboard)\invoices",
    "app\(dashboard)\reports",
    "app\(dashboard)\settings",
    "app\(dashboard)\settings\cameras",
    "app\(dashboard)\settings\thresholds",
    "app\api",
    "components\cameras",
    "components\events",
    "components\alerts",
    "components\shared",
    "components\dev-only",
    "lib",
    "types",
    "__fixtures__"
)

foreach ($Dir in $Dirs) {
    $Path = Join-Path $BaseDir $Dir
    if (!(Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

$Files = @(
    "app\(dashboard)\layout.tsx", "app\(dashboard)\page.tsx", 
    "app\(dashboard)\events\page.tsx", "app\(dashboard)\events\[eventId]\page.tsx",
    "app\(dashboard)\alerts\page.tsx", "app\(dashboard)\products\page.tsx",
    "app\(dashboard)\employees\page.tsx", "app\(dashboard)\employees\[employeeId]\page.tsx",
    "app\(dashboard)\invoices\page.tsx", "app\(dashboard)\reports\page.tsx",
    "app\(dashboard)\settings\page.tsx", "app\(dashboard)\settings\cameras\page.tsx", "app\(dashboard)\settings\thresholds\page.tsx",
    "components\cameras\CameraTile.tsx", "components\cameras\CameraVideoOverlay.tsx", "components\cameras\CameraOperationsHud.tsx",
    "components\cameras\RoiPolygonEditor.tsx", "components\cameras\PtzControls.tsx", "components\cameras\CameraStatusDot.tsx", "components\cameras\AddCameraModal.tsx",
    "components\events\EventRow.tsx", "components\events\EventDetailPanel.tsx", "components\events\MathBreakdown.tsx",
    "components\alerts\AlertCard.tsx", "components\alerts\ResolutionModal.tsx", "components\alerts\SignaturePad.tsx",
    "components\shared\KpiTile.tsx", "components\shared\SeverityBadge.tsx", "components\shared\EmptyState.tsx",
    "components\dev-only\SimulatorDrawer.tsx", "components\dev-only\InjectFakeEventButton.tsx",
    "lib\api-client.ts", "lib\websocket-client.ts", "lib\design-tokens.ts",
    "types\index.ts"
)

foreach ($File in $Files) {
    $Path = Join-Path $BaseDir $File
    if (!(Test-Path $Path)) {
        New-Item -ItemType File -Force -Path $Path | Out-Null
    }
}
