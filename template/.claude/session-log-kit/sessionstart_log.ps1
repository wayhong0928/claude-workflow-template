# 通用 SessionStart hook：注入「目前專案」session_log.md 的最新 3 筆
# 不寫死路徑：先看 CLAUDE_PROJECT_DIR（Claude Code 提供給 hook 的環境變數），再退回目前工作目錄。
# 依序找 <root>\session_log.md、<root>\notes\session_log.md，找不到就安靜結束（不報錯）。
# 編碼要求：本檔必須存為 UTF-8 with BOM（PowerShell 5.1 才能正確讀中文）
$root = if ($env:CLAUDE_PROJECT_DIR) { $env:CLAUDE_PROJECT_DIR } else { (Get-Location).Path }
$candidates = @((Join-Path $root 'session_log.md'), (Join-Path $root 'notes\session_log.md'))
$logPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($logPath) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $lines = Get-Content -Path $logPath -Encoding UTF8

    # 找出所有 "## YYYY-MM-DD..." 標題列的位置與日期
    $blocks = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^## (\d{4}-\d{2}-\d{2})') {
            $blocks += [PSCustomObject]@{ Start = $i; Date = $Matches[1] }
        }
    }

    if ($blocks.Count -eq 0) {
        $content = $lines -join "`n"
    } else {
        for ($j = 0; $j -lt $blocks.Count; $j++) {
            if ($j -lt $blocks.Count - 1) { $end = $blocks[$j + 1].Start - 1 } else { $end = $lines.Count - 1 }
            $blocks[$j] | Add-Member -NotePropertyName End -NotePropertyValue $end
        }
        # 取日期最新 3 筆；PS 5.1 Sort-Object 不穩定，同日期以檔內位置為次鍵（越上面越新）
        $newest = $blocks | Sort-Object @{Expression = 'Date'; Descending = $true }, @{Expression = 'Start'; Descending = $false } | Select-Object -First 3
        # 最新 1 筆全文；第 2、3 筆只放標題列加「下一步」段（舊格式找「剩什麼未完成」），
        # 都找不到就只放標題。要看全文請讀檔。
        $parts = @()
        $k = 0
        foreach ($b in $newest) {
            if ($k -eq 0) {
                $parts += ($lines[$b.Start..$b.End] -join "`n")
            } else {
                $seg = @($lines[$b.Start])
                $nextIdx = -1
                for ($x = $b.Start + 1; $x -le $b.End; $x++) {
                    if ($lines[$x] -match '^\s*(\*\*)?(下一步|剩什麼未完成)') { $nextIdx = $x; break }
                }
                if ($nextIdx -ge 0) {
                    $stop = [Math]::Min($b.End, $nextIdx + 6)
                    for ($x = $nextIdx; $x -le $stop; $x++) {
                        if ($x -gt $nextIdx -and $lines[$x] -match '^(\*\*|---|## )') { break }
                        $seg += $lines[$x]
                    }
                }
                $parts += (($seg -join "`n").TrimEnd() + "`n")
            }
            $k++
        }
        $content = $parts -join "`n"
    }

    # 維護提醒：只在「檔案夠大」而且「真的有東西可歸檔」時才出現。
    # 只看檔案大小的話，提醒會一直亮著卻無法執行（保底保留的最新 3 筆本身就不小），
    # 等於每個 session 白付一次 token 讀一段做不到的指示。所以門檻設 80KB，並且
    # 先確認真的有記錄落在歸檔窗口之外才提醒，提醒裡也直接講清楚有幾筆可搬。
    $sizeNote = ''
    $archiveWindowDays = 7
    if ((Get-Item $logPath).Length -gt 81920 -and $blocks.Count -gt 3) {
        $cutoff = (Get-Date).AddDays(-$archiveWindowDays).ToString('yyyy-MM-dd')
        $archivable = @($blocks | Where-Object { $_.Date -lt $cutoff -and ($newest -notcontains $_) })
        if ($archivable.Count -gt 0) {
            $sizeNote = "`n[維護提醒] session_log.md 已超過 80KB，其中 $($archivable.Count) 筆早於 $cutoff，可以歸檔。歸檔只是把整段原文搬進 session_log_archive.md，不刪任何內容，最新 3 筆一律保留。執行：powershell -File `"$PSScriptRoot\archive_session_log.ps1`""
        }
    }
    # 標題遺失檢查：在頂部加新紀錄時，有可能弄掉下面一筆的 "## " 標題，兩筆內容因此併成一筆。
    # 判斷：同一個標題底下出現兩次以上「**做了什麼**」，或第一個標題之前就有，就提醒。
    # 不直接比總數，因為舊格式的紀錄沒有「做了什麼」段，比總數會一直誤報。
    $lostNote = ''
    $doneRe = '^\s*\*\*做了什麼'
    $suspects = @()
    $firstStart = if ($blocks.Count -gt 0) { $blocks[0].Start } else { $lines.Count }
    for ($x = 0; $x -lt $firstStart; $x++) {
        if ($lines[$x] -match $doneRe) { $suspects += "第 $($x + 1) 行（第一個標題之前）"; break }
    }
    foreach ($b in $blocks) {
        $hits = @()
        for ($x = $b.Start + 1; $x -le $b.End; $x++) {
            if ($lines[$x] -match $doneRe) { $hits += $x }
        }
        if ($hits.Count -ge 2) { $suspects += "第 $($hits[1] + 1) 行（在「$($lines[$b.Start])」底下）" }
    }
    if ($suspects.Count -gt 0) {
        $lostNote = "`n[標題遺失提醒] session_log 有 $($suspects.Count) 處「做了什麼」前面少了 ## 標題，可能是加新紀錄時把下面一筆的標題弄掉了：$($suspects -join '；')。請對照備份或版本紀錄補回標題。"
    }
    $header = "=== SESSION LOG：最新 1 筆全文，前 2 筆只列標題與下一步（完整記錄在 $logPath，需要時再讀檔）===$lostNote$sizeNote`n"
    $obj = @{ hookSpecificOutput = @{ hookEventName = 'SessionStart'; additionalContext = ($header + $content) } }
    $obj | ConvertTo-Json -Depth 3 -Compress
}
