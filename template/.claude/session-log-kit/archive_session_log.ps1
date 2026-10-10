# session_log.md 歸檔工具：把 7 天前的舊記錄移入 session_log_archive.md
# 保護規則：無論多舊，永遠保留最新 3 筆在 log 內（與 SessionStart hook 注入量一致）。
# 歸檔不刪任何內容——整段原文搬進 session_log_archive.md，只是不再被自動注入。
# 用法：powershell -File archive_session_log.ps1 [-LogPath <log完整路徑>] [-Days 7]
#       不給 LogPath 時，依 CLAUDE_PROJECT_DIR 或目前目錄自動尋找（同 hook 邏輯）。
# 編碼要求：本檔必須存為 UTF-8 with BOM
#
# 兩個設計決定：
# (1) 預設窗口 7 天。窗口要跟實際寫入密度對得起來：天天寫的專案，窗口太長就永遠搬不動任何東西。
# (2) 寫檔用 UTF8Encoding($false)，不往 .md 開頭寫 BOM。BOM 會卡住任何用
#     '^## ' 解析的工具（PowerShell 讀檔時會吃掉 BOM，但 grep 與 Python 會
#     漏掉檔案的第一筆記錄）。要求 UTF-8 with BOM 的對象是 .ps1 檔本身，不是它
#     產出的 .md。
param(
    [string]$LogPath = '',
    [int]$Days = 7
)

if (-not $LogPath) {
    $root = if ($env:CLAUDE_PROJECT_DIR) { $env:CLAUDE_PROJECT_DIR } else { (Get-Location).Path }
    $candidates = @((Join-Path $root 'session_log.md'), (Join-Path $root 'notes\session_log.md'))
    $LogPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $LogPath -or -not (Test-Path $LogPath)) { Write-Output '找不到 session_log.md，未執行任何動作。'; exit 0 }

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$lines = Get-Content -Path $LogPath -Encoding UTF8
$cutoff = (Get-Date).AddDays(-$Days).ToString('yyyy-MM-dd')

# 解析區塊（標題 ## YYYY-MM-DD ...）
$blocks = @()
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^## (\d{4}-\d{2}-\d{2})') {
        $blocks += [PSCustomObject]@{ Start = $i; Date = $Matches[1] }
    }
}
if ($blocks.Count -le 3) { Write-Output "記錄僅 $($blocks.Count) 筆（≤3），不需歸檔。"; exit 0 }

for ($j = 0; $j -lt $blocks.Count; $j++) {
    if ($j -lt $blocks.Count - 1) { $end = $blocks[$j + 1].Start - 1 } else { $end = $lines.Count - 1 }
    $blocks[$j] | Add-Member -NotePropertyName End -NotePropertyValue $end
}

# 最新 3 筆永遠保留（同日期以檔內位置為次鍵，越上面越新）
$newest3 = ($blocks | Sort-Object @{Expression = 'Date'; Descending = $true }, @{Expression = 'Start'; Descending = $false } | Select-Object -First 3)
$toMove = $blocks | Where-Object { $_.Date -lt $cutoff -and ($newest3 -notcontains $_) }
if (-not $toMove) { Write-Output "沒有早於 $cutoff 的可歸檔記錄（最新 3 筆一律保留）。"; exit 0 }

$archivePath = Join-Path (Split-Path $LogPath) 'session_log_archive.md'
$stamp = Get-Date -Format 'yyyy-MM-dd'
$movedText = "`r`n<!-- 歸檔於 $stamp（來自 session_log.md，早於 $cutoff 的記錄）-->`r`n" +
    (($toMove | ForEach-Object { ($lines[$_.Start..$_.End] -join "`r`n") }) -join "`r`n")

$enc = New-Object System.Text.UTF8Encoding $false   # $false = 不寫 BOM，見檔頭修正 (2)
if (Test-Path $archivePath) {
    [System.IO.File]::AppendAllText($archivePath, $movedText, $enc)
} else {
    [System.IO.File]::WriteAllText($archivePath, "# Session Log Archive`r`n" + $movedText, $enc)
}

# 重寫 log：保留非歸檔區塊與檔頭，維持原有順序
$moveStarts = @($toMove | ForEach-Object { $_.Start })
$keep = New-Object System.Collections.Generic.List[string]
$firstBlock = ($blocks | Sort-Object Start | Select-Object -First 1).Start
if ($firstBlock -gt 0) { $lines[0..($firstBlock - 1)] | ForEach-Object { $keep.Add($_) } }
foreach ($b in ($blocks | Sort-Object Start)) {
    if ($moveStarts -notcontains $b.Start) { $lines[$b.Start..$b.End] | ForEach-Object { $keep.Add($_) } }
}
[System.IO.File]::WriteAllText($LogPath, (($keep -join "`r`n") + "`r`n"), $enc)

Write-Output ("已歸檔 {0} 筆（早於 {1}）至 {2}；log 保留 {3} 筆。" -f @($toMove).Count, $cutoff, $archivePath, ($blocks.Count - @($toMove).Count))
