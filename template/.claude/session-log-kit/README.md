# session_log：跨 session 接力

Claude Code 每開一個新 session 都不記得上次做到哪。這個套件讓開場自動帶入上次的紀錄，收尾時用固定格式補一筆。三支都是 Python，只用標準函式庫，在 Windows 和 WSL2（Ubuntu）上跑過測試，macOS 沒測過。

- `sessionstart_log.py`：開場時由 hook 執行，把 `session_log.md` 最新幾筆注入給 Claude。
- `add_session_log.py`：把一筆新紀錄插到 `session_log.md` 最上面，並檢查格式。
- `archive_session_log.py`：log 太長時，把舊紀錄搬到 `session_log_archive.md`。

設定、`session_log.md`、`TODO.md` 和 CLAUDE.md 裡的接力說明，`install.py` 都裝好了，不用再手動設定。

## 開場注入什麼

- 找專案根目錄的 `session_log.md`，沒有的話找 `notes/session_log.md`，都沒有就什麼都不做。
- 取日期最新的 3 筆：最新 1 筆放全文，第 2、3 筆只放標題和「下一步」那段。要看更早的就去讀檔。
- 同一個標題底下出現兩次「做了什麼」時，注入內容會多一行「標題遺失提醒」，代表某次插入弄掉了一個 `## ` 標題，要對照備份或版本紀錄補回。
- log 超過 80KB、而且有 7 天前的紀錄時，注入內容會多一行維護提醒，照提醒跑 `archive_session_log.py`。

## 每筆的寫法

```
## 2026-10-12 | 文獻筆記：第二章三篇

**做了什麼**：
- 讀完三篇自我調節學習的論文，筆記放在 notes/ch2/

**決定了什麼**：
- 引用格式統一用 APA 第七版，因為系上規定

**下一步**：
- TODO「進行中」第一條：補第四篇的頁碼
```

- 標題 `## YYYY-MM-DD | 主題`，下面固定三段，合計 600 字內（不含空白）。寫不出「下一步」的紀錄等於沒寫。
- 「決定了什麼」附一句理由；「下一步」只寫做到哪裡中斷、指向 TODO 的哪一條，不重抄。使用者要做的事寫進 TODO，開場只帶出最新 3 筆，留在 log 裡很快就會被擠掉。
- 同一天同一主題合併成一筆。驗收過程、指令輸出、查證細節不寫，檔案本身就有。

## 寫入方式

新紀錄先存成暫存 .md，再在專案根目錄跑：

```
python .claude/session-log-kit/add_session_log.py session_log.md <暫存檔>
```

這台電腦的 Python 指令如果是 `python3` 或 `py`，就換成那個（下面的歸檔也一樣）。腳本會插到最新一筆之前，並檢查標題格式、三段齊全、沒有控制字元、600 字內（確定要超過加 `--allow-long`）；任一項不過就不寫入並印出原因，寫完會重讀確認標題數剛好多 1。「下一步」有以「使用者：」或「你：」開頭的行，寫入後會提醒你把它也記進 TODO。

不要臨場寫腳本或手動貼上：常見的失誤是把下面一筆的標題弄掉，或字串跳脫把內容寫壞。

## 歸檔

```
python .claude/session-log-kit/archive_session_log.py
```

把 7 天前的紀錄搬進 `session_log_archive.md`（開場不會讀這份），最新 3 筆一定保留。要換天數加 `--days 14`；log 不在專案根目錄時，把路徑接在後面。

想順便整理時：從最舊的一筆往新看，還有效的決定寫進 CLAUDE.md，教訓寫回 `.claude/rules/dispatch-and-verify.md`，沒做完又不在 TODO 裡的事補進 TODO，最後再歸檔。舊紀錄照原文搬，不刪不改寫。

## 舊版的 .ps1

舊版用 `sessionstart_log.ps1`、`archive_session_log.ps1`，要 PowerShell 才能跑。重跑一次 `install.py` 會把它們備份後收掉，settings.json 裡的開場 hook 也會換成 Python 版。
