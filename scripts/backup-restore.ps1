# scripts/backup-restore.ps1
# Restore Cloud SQL from a backup or point-in-time
# Usage: powershell -ExecutionPolicy Bypass -File scripts\backup-restore.ps1
#
# DANGER: This replaces ALL data in the instance with the backup contents.
# See docs/disaster-recovery-runbook.md for full procedures.

$GCLOUD = "C:\apps\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
$PROJECT = "emai-dev-01"
$INSTANCE = "emai-db"

Write-Host "=== ClassBridge: Restore from Backup ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "WARNING: This is a destructive operation!" -ForegroundColor Red
Write-Host ""

# Show available backups
Write-Host "Available backups:" -ForegroundColor Yellow
& $GCLOUD sql backups list --instance=$INSTANCE --project=$PROJECT --limit=10 `
    --format="table(id,windowStartTime.date('%Y-%m-%d %H:%M UTC'),status,type)"

Write-Host ""
Write-Host "Options:"
Write-Host "  1. Restore from a backup ID (replaces current data in-place)"
Write-Host "  2. Point-in-time recovery (clones to a NEW instance — safer)"
Write-Host ""
$choice = Read-Host "Enter choice (1 or 2)"

if ($choice -eq "2") {
    # PITR — clones to new instance (non-destructive to original)
    $timestamp = Read-Host "Enter UTC timestamp to restore to (e.g. 2026-02-15T12:00:00Z)"
    $newInstance = "${INSTANCE}-restored"

    Write-Host ""
    Write-Host "CONFIRMATION" -ForegroundColor Red
    Write-Host "  Action:       Clone to point-in-time $timestamp" -ForegroundColor Red
    Write-Host "  Source:       $INSTANCE" -ForegroundColor Red
    Write-Host "  Destination:  $newInstance (new instance)" -ForegroundColor Red
    Write-Host ""
    $confirm = Read-Host "Type 'RESTORE' to proceed"
    if ($confirm -ne "RESTORE") {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }

    Write-Host "Cloning instance to $timestamp..." -ForegroundColor Yellow
    & $GCLOUD sql instances clone $INSTANCE $newInstance `
        --project=$PROJECT `
        --point-in-time=$timestamp

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "PITR clone created: $newInstance" -ForegroundColor Green
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Cyan
        Write-Host "  1. Verify data in $newInstance"
        Write-Host "  2. Update DATABASE_URL secret to point to $newInstance"
        Write-Host "  3. Redeploy Cloud Run: gcloud run services update classbridge ..."
        Write-Host "  4. Once verified, delete the old instance if no longer needed"
        Write-Host "  See docs/disaster-recovery-runbook.md for details."
    } else {
        Write-Host "ERROR: PITR clone failed." -ForegroundColor Red
        exit 1
    }

} elseif ($choice -eq "1") {
    # Direct restore — destructive to current instance
    $backupId = Read-Host "Enter the backup ID to restore from"

    Write-Host ""
    Write-Host "DANGER — FINAL CONFIRMATION" -ForegroundColor Red
    Write-Host "  Action:    Restore backup ID $backupId" -ForegroundColor Red
    Write-Host "  Instance:  $INSTANCE" -ForegroundColor Red
    Write-Host "  This REPLACES all current data and CANNOT be undone." -ForegroundColor Red
    Write-Host ""
    $confirm = Read-Host "Type 'RESTORE' to proceed"
    if ($confirm -ne "RESTORE") {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }

    Write-Host "Restoring backup $backupId..." -ForegroundColor Yellow
    & $GCLOUD sql backups restore $backupId `
        --restore-instance=$INSTANCE `
        --project=$PROJECT `
        --quiet

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Restore completed." -ForegroundColor Green
        Write-Host "Verify application health immediately:" -ForegroundColor Cyan
        Write-Host "  1. Check https://www.classbridge.ca/health"
        Write-Host "  2. Log in and verify data"
    } else {
        Write-Host "ERROR: Restore failed." -ForegroundColor Red
        exit 1
    }

} else {
    Write-Host "Invalid choice. Exiting." -ForegroundColor Yellow
    exit 0
}
