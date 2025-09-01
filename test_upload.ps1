# Test upload endpoint
$fileBytes = [System.IO.File]::ReadAllBytes("sample.csv")
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"

$bodyLines = @(
    "--$boundary",
    "Content-Disposition: form-data; name=`"user_id`"",
    "",
    "user_TESTCURSOR1",
    "--$boundary",
    "Content-Disposition: form-data; name=`"file`"; filename=`"sample.csv`"",
    "Content-Type: text/csv",
    "",
    [System.Text.Encoding]::UTF8.GetString($fileBytes),
    "--$boundary--",
    ""
)

$body = $bodyLines -join $LF

try {
    $response = Invoke-WebRequest -Uri "https://backend.retainwiseanalytics.com/upload/csv" -Method POST -Headers @{"Content-Type"="multipart/form-data; boundary=$boundary"} -Body $body
    Write-Host "Status Code: $($response.StatusCode)"
    Write-Host "Response: $($response.Content)"
} catch {
    Write-Host "Error: $($_.Exception.Message)"
    Write-Host "Status Code: $($_.Exception.Response.StatusCode)"
    Write-Host "Response: $($_.Exception.Response.Content)"
} 