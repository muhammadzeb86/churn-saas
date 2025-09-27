# Final upload test with real user ID
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"

# Create multipart form data with real user ID
$bodyLines = @(
    "--$boundary",
    "Content-Disposition: form-data; name=`"user_id`"",
    "",
    "user_3097FrGQiUsUdFUuXy5vpbdk7zg",
    "--$boundary",
    "Content-Disposition: form-data; name=`"file`"; filename=`"sample.csv`"",
    "Content-Type: text/csv",
    "",
    "customerID,tenure,MonthlyCharges`nC1,5,72.5`nC2,3,65.0`nC3,12,88.1",
    "--$boundary--",
    ""
)

$body = $bodyLines -join $LF

try {
    Write-Host "Testing upload endpoint with real user ID: user_3097FrGQiUsUdFUuXy5vpbdk7zg"
    $response = Invoke-WebRequest -Uri "https://api.retainwiseanalytics.com/upload/csv" -Method POST -Headers @{"Content-Type"="multipart/form-data; boundary=$boundary"} -Body $body
    Write-Host "✅ SUCCESS!"
    Write-Host "Status Code: $($response.StatusCode)"
    Write-Host "Response: $($response.Content)"
} catch {
    Write-Host "❌ ERROR: $($_.Exception.Message)"
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
