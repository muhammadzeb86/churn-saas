# Sync user via API
$body = @{
    id = "user_3097FrGQiUsUdFUuXy5vpbdk7zg"
    email_addresses = @(
        @{
            email_address = "tahir_zaib86@hotmail.com"
        }
    )
    first_name = "Muhammad"
    last_name = "Zeb"
} | ConvertTo-Json -Depth 3

try {
    Write-Host "Syncing user with ID: user_3097FrGQiUsUdFUuXy5vpbdk7zg"
    $response = Invoke-WebRequest -Uri "https://api.retainwiseanalytics.com/auth/sync_user" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing
    Write-Host "Status Code: $($response.StatusCode)"
    Write-Host "Response: $($response.Content)"
} catch {
    Write-Host "Error: $($_.Exception.Message)"
    if ($_.Exception.Response -ne $null) {
        Write-Host "Status Code: $($_.Exception.Response.StatusCode)"
        try {
            $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Write-Host "Response Body: $($sr.ReadToEnd())"
        } catch {
            Write-Host "Could not read response body"
        }
    }
} 
