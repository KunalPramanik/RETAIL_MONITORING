$BaseDir = "c:\Users\DELL\.gemini\antigravity\scratch\N\retail-exit-backend\src"

# Define directories
$Dirs = @(
    "api",
    "ml\level1_detection",
    "ml\level2_classification",
    "ml\level3_liveness",
    "ml\level4_counting",
    "ml\level5_tracking",
    "ml\face_recognition",
    "ml\ocr",
    "engine",
    "db\models",
    "services",
    "auth",
    "core"
)

foreach ($Dir in $Dirs) {
    $Path = Join-Path $BaseDir $Dir
    if (!(Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

$Files = @(
    "api\cameras.py", "api\events.py", "api\alerts.py", "api\products.py", "api\employees.py", "api\invoices.py", "api\reports.py", "api\settings.py",
    "ml\level1_detection\vision_service.py",
    "ml\level2_classification\fixture_classifier.py",
    "ml\level3_liveness\liveness_service.py", "ml\level3_liveness\static_image_service.py",
    "ml\level4_counting\pack_size_resolver.py",
    "ml\level5_tracking\tracker_service.py",
    "ml\face_recognition\face_service.py",
    "ml\ocr\invoice_ocr_service.py",
    "ml\model_config.py",
    "engine\fusion_engine.py", "engine\verdict_engine.py", "engine\dispatch_engine.py", "engine\inventory_ledger_engine.py",
    "services\camera_discovery_service.py", "services\camera_heartbeat_service.py", "services\alarm_dispatch_service.py", "services\websocket_gateway.py",
    "auth\jwt_handler.py", "auth\rbac.py",
    "core\config.py", "core\logging.py"
)

foreach ($File in $Files) {
    $Path = Join-Path $BaseDir $File
    if (!(Test-Path $Path)) {
        New-Item -ItemType File -Force -Path $Path | Out-Null
    }
}
