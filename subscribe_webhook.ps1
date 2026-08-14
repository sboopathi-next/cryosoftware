# ================================
# Tempo Webhook Subscription
# ================================

$tempoToken = "YOUR_TEMPO_ACCESS_TOKEN"

# Your publicly accessible HTTPS endpoint
$webhookUrl = "https://your-domain.com/api/tempo/webhook"

$headers = @{
    "Authorization" = "Bearer $tempoToken"
    "Content-Type"  = "application/json"
    "Accept"        = "application/json"
}

$events = @(
    @{
        name        = "KARMIC Tempo Worklog Created"
        description = "KARMIC - Tempo worklog created events"
        event       = "worklog.created"
    },
    @{
        name        = "KARMIC Tempo Worklog Updated"
        description = "KARMIC - Tempo worklog updated events"
        event       = "worklog.updated"
    },
    @{
        name        = "KARMIC Tempo Worklog Deleted"
        description = "KARMIC - Tempo worklog deleted events"
        event       = "worklog.deleted"
    }
)

foreach ($item in $events) {

    $body = @{
        url         = $webhookUrl
        name        = $item.name
        description = $item.description
        event       = $item.event
    } | ConvertTo-Json

    Write-Host ""
    Write-Host "Creating subscription: $($item.event)" -ForegroundColor Cyan

    try {

        $response = Invoke-RestMethod `
            -Method POST `
            -Uri "https://api.tempo.io/4/webhooks/subscriptions" `
            -Headers $headers `
            -Body $body

        Write-Host "SUCCESS" -ForegroundColor Green

        $response | ConvertTo-Json -Depth 10

    }
    catch {

        Write-Host "FAILED" -ForegroundColor Red
        Write-Host $_.Exception.Message
    }
}