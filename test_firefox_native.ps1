# KlipVault Firefox Native Messaging Diagnostic Script
# Run this in PowerShell to test if the native host works

Write-Host "=== KlipVault Firefox Native Host Diagnostic ===" -ForegroundColor Cyan
Write-Host ""

$firefoxManifestPath = "$env:APPDATA\Mozilla\NativeMessagingHosts\klipvault_host.json"
$chromeManifestPath = "$env:LOCALAPPDATA\KlipVault\NativeMessagingHosts\klipvault_host.json"
$firefoxHostDir = "$env:APPDATA\Mozilla\NativeMessagingHosts"

# 1. Check Firefox manifest
Write-Host "1. Checking Firefox manifest..." -ForegroundColor Yellow
if (Test-Path $firefoxManifestPath) {
    Write-Host "   ✅ Found: $firefoxManifestPath" -ForegroundColor Green
    $manifest = Get-Content $firefoxManifestPath -Raw | ConvertFrom-Json
    Write-Host "   Name: $($manifest.name)"
    Write-Host "   Path: $($manifest.path)"
    Write-Host "   Allowed extensions: $($manifest.allowed_extensions -join ', ')"
} else {
    Write-Host "   ❌ NOT FOUND: $firefoxManifestPath" -ForegroundColor Red
}
Write-Host ""

# 2. Check if the host script/bat exists
Write-Host "2. Checking host executable..." -ForegroundColor Yellow
$batPath = "$firefoxHostDir\klipvault_host.bat"
$pyPath = "$firefoxHostDir\klipvault_host.py"
if (Test-Path $batPath) {
    Write-Host "   ✅ Found .bat: $batPath" -ForegroundColor Green
    Write-Host "   Content:" -ForegroundColor Gray
    Get-Content $batPath | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
} else {
    Write-Host "   ❌ .bat NOT FOUND" -ForegroundColor Red
}
if (Test-Path $pyPath) {
    Write-Host "   ✅ Found .py: $pyPath" -ForegroundColor Green
    $hasHomeFunc = Select-String -Path $pyPath -Pattern "_get_windows_home" -Quiet
    if ($hasHomeFunc) {
        Write-Host "   ✅ Script has _get_windows_home() fix" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Script MISSING _get_windows_home() — old version!" -ForegroundColor Red
    }
} else {
    Write-Host "   ❌ .py NOT FOUND" -ForegroundColor Red
}
Write-Host ""

# 3. Test native host directly (simulate Firefox)
Write-Host "3. Testing native host directly..." -ForegroundColor Yellow
if (Test-Path $batPath) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $batPath
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $proc.Start() | Out-Null

    # Send a ping message (4-byte length prefix + JSON)
    $pingMsg = '{"action":"ping"}'
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($pingMsg)
    $lengthBytes = [BitConverter]::GetBytes([uint32]$bytes.Length)
    $proc.StandardInput.BaseStream.Write($lengthBytes, 0, 4)
    $proc.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
    $proc.StandardInput.BaseStream.Flush()

    # Read response (4-byte length + JSON)
    $proc.StandardOutput.BaseStream.ReadTimeout = 5000
    try {
        $respLenBytes = New-Object byte[] 4
        $read = $proc.StandardOutput.BaseStream.Read($respLenBytes, 0, 4)
        if ($read -eq 4) {
            $respLen = [BitConverter]::ToUInt32($respLenBytes, 0)
            $respBytes = New-Object byte[] $respLen
            $read2 = $proc.StandardOutput.BaseStream.Read($respBytes, 0, $respLen)
            $response = [System.Text.Encoding]::UTF8.GetString($respBytes)
            Write-Host "   ✅ Native host responded:" -ForegroundColor Green
            $response | ConvertFrom-Json | ConvertTo-Json -Depth 10 | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
        } else {
            Write-Host "   ❌ No response (read $read bytes)" -ForegroundColor Red
        }
    } catch {
        Write-Host "   ❌ Timeout or error: $_" -ForegroundColor Red
    }

    # Check stderr
    $stderr = $proc.StandardError.ReadToEnd()
    if ($stderr) {
        Write-Host "   Stderr output:" -ForegroundColor Magenta
        $stderr -split "`n" | ForEach-Object { Write-Host "      $_" -ForegroundColor Magenta }
    }

    # Cleanup
    if (-not $proc.HasExited) {
        $proc.Kill()
    }
} else {
    Write-Host "   ❌ Cannot test — .bat not found" -ForegroundColor Red
}
Write-Host ""

# 4. Check for log files
Write-Host "4. Checking for log files..." -ForegroundColor Yellow
$logPaths = @(
    "$firefoxHostDir\klipvault_host.log",
    "$env:TEMP\klipvault_host.log",
    "$env:LOCALAPPDATA\KlipVault\NativeMessagingHosts\klipvault_host.log"
)
$foundLog = $false
foreach ($lp in $logPaths) {
    if (Test-Path $lp) {
        Write-Host "   ✅ Found log: $lp" -ForegroundColor Green
        Write-Host "   Last 20 lines:" -ForegroundColor Gray
        Get-Content $lp -Tail 20 | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
        $foundLog = $true
    }
}
if (-not $foundLog) {
    Write-Host "   ⚠️  No log files found" -ForegroundColor Yellow
}
Write-Host ""

# 5. Check Firefox extension ID
Write-Host "5. Firefox extension ID check..." -ForegroundColor Yellow
$firefoxExtDir = "$env:APPDATA\Mozilla\Firefox\Profiles"
if (Test-Path $firefoxExtDir) {
    $profiles = Get-ChildItem $firefoxExtDir -Directory
    foreach ($profile in $profiles) {
        $extFile = "$($profile.FullName)\extensions\klipvault@velocityforge.com"
        $jsonFile = "$($profile.FullName)\extensions.json"
        if (Test-Path $extFile) {
            Write-Host "   ✅ Extension found in profile: $($profile.Name)" -ForegroundColor Green
        }
        if (Test-Path $jsonFile) {
            $hasClipvault = Select-String -Path $jsonFile -Pattern "klipvault" -Quiet
            if ($hasClipvault) {
                Write-Host "   ✅ clipvault referenced in extensions.json for: $($profile.Name)" -ForegroundColor Green
            }
        }
    }
} else {
    Write-Host "   ⚠️  Firefox profiles dir not found" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "=== End Diagnostic ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "If the native host responded to the ping test (step 3) but Firefox still fails," -ForegroundColor White
Write-Host "the issue is Firefox-specific (manifest path, extension ID mismatch, or .bat support)." -ForegroundColor White
Write-Host "If the native host did NOT respond, check the stderr output above for Python errors." -ForegroundColor White
