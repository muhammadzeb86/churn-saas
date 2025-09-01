# Simple test with minimal multipart form data
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"

# Create a simple multipart form data
$bodyLines = @(
    "--$boundary",
    "Content-Disposition: form-data; name=`"user_id`"",
    "",
    "user_TESTCURSOR1",
    "--$boundary",
    "Content-Disposition: form-data; name=`"file`"; filename=`"test.csv`"",
    "Content-Type: text/csv",
    "",
    "customerID,tenure,MonthlyCharges`nC1,5,72.5",
    "--$boundary--",
    ""
)

$body = $bodyLines -join $LF

try {
    Write-Host "Testing upload endpoint..."
    $response = Invoke-WebRequest -Uri "https://backend.retainwiseanalytics.com/upload/csv" -Method POST -Headers @{"Content-Type"="multipart/form-data; boundary=$boundary"} -Body $body
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