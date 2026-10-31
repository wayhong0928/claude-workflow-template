# todo plugin

把幾個專案的 TODO.md 集中起來看。Python 腳本 `scripts/todo_core.py` 讀各專案的 TODO、session_log 最新一筆的下一步、goal 計畫檔，整理成一份 `todo_index.json`，同時負責開場清單與格式檢查；側欄 mod 只讀那份 index 畫畫面。

| 功能 | 由誰做 | 什麼時候 |
|---|---|---|
| 開場清單（注入 session 開頭的 context） | command hook 跑 `todo_core.py render` | SessionStart |
| 重產 `todo_index.json` | command hook 跑 `todo_core.py index` | SessionStart、Edit／Write 之後、每次送出提示 |
| 第一行格式檢查，只警告、不擋 | command hook 跑 `todo_lint.py` | Edit／Write 改到設定檔列的 TODO 時 |
| `/todo` 指令、TODO 側欄、輸入框上方的下一步 | mod（`hooks/register.tsx`） | 一直在 |

沒有 mod 可用的環境（Claude Code 版本太舊，或關掉了 mod），開場清單與格式檢查照樣有。

## 需要什麼

- Python 3.8 以上，只用標準庫。hook 依序找 `python3`、`python`、`py`，第一個能跑 3.8 以上的就用；都找不到就安靜跳過，不擋 session。
- command hook 用 sh 執行。macOS、Linux 不用另外裝；Windows 要有 Git Bash（裝 Git for Windows 就有）。沒有 Git Bash 時 Claude Code 會改用 PowerShell，這幾個 hook 會失敗，側欄也就沒有新的 index 可讀。
- 側欄 mod 要 Claude Code v2.1.287 以上。

## 安裝

在 Claude Code 裡打：

```
/plugin marketplace add wayhong0928/claude-workflow-template
/plugin install todo@workflow-kit
```

公司電腦擋 plugin 的話，可以改用根目錄的 `install.py --todo`（備用裝法，見[根目錄 README](../README.md#installpy-會做什麼)）：它把 `scripts/` 的兩支腳本複製到專案的 `.claude/todo/`，只裝開場清單與格式檢查，沒有 index 和側欄。設定檔的位置與寫法兩條路線一樣。

裝好後寫設定檔（下一節）。同一個 marketplace 的 `workflow-kit` 有 `/workflow-kit:setup` 可以幫你產生；不裝它就照下面手寫。

## 設定檔

位置是 Claude Code 的設定資料夾：有設 `CLAUDE_CONFIG_DIR` 就是那裡，沒設就是家目錄下的 `.claude`。檔名 `todo.config.json`，可以從 `todo.config.example.json` 複製一份改：

```json
{
  "home": "my-thesis",
  "projects": [
    { "name": "my-thesis", "root": "~/projects/my-thesis", "todo": ["TODO.md"], "log": "session_log.md" }
  ]
}
```

| 欄位 | 預設 | 說明 |
|---|---|---|
| `home` | 第一個專案 | session 不在任何專案底下時，開場清單把它當成所在專案，全列這個專案，其他專案只列條數與快到期的。側欄在這個專案或專案外開時列全部專案，在其他專案開只列那個專案。沒設 session_log 的專案，下一步看 home 專案的 |
| `dueSoonDays` | 7 | 開場清單裡「其他專案」要展開幾天內到期的條目 |
| `staleDays` | 14 | 建立日或修改日（取較晚的）超過幾天，標「待驗現況」 |
| `maxFirstLine` | 60 | 第一行扣掉欄位括號後的字數上限 |
| `wslPrefix` | `/mnt` | 在 WSL 裡把 `E:/x` 換成 `/mnt/e/x`；寫 `/mnt` 或 `/mnt/d` 都可以 |
| `planGlob` | `計畫_*.md` | goal 計畫檔的檔名樣式 |
| `views` | 四種全開 | 側欄顯示哪些版面、照什麼順序。寫代號 `mine`、`project`、`time`、`goal`，也認分頁上的短名稱「你」「專案」「時間」「Goal」，例如 `["mine", "goal"]`；按鍵照這個順序編 1、2…。不認得的值會略過，全部不認得就四種全開 |
| `projects[].name` | 資料夾名 | 顯示用的專案名 |
| `projects[].root` | 必填 | 專案資料夾，可以寫 `~` |
| `projects[].todo` | `["TODO.md"]` | TODO 檔，相對 `root`；可以列好幾個 |
| `projects[].log` | 不設 | session_log，相對 `root`；不設就不顯示這個專案的下一步 |
| `projects[].skipDirs` | `[]` | 找計畫檔與有效期檔時不進去的資料夾名稱，例如書庫、概念卡這類大量內容資料夾 |

設定檔列了但讀不到的 TODO，`lint` 會報「讀不到」，不會當成空清單略過。

## 讀哪些檔、寫哪些檔

讀：

- 設定檔與 `projects[].todo`、`projects[].log` 列的檔。
- 各專案 `root` 底下的 `.md`：找 `planGlob` 的計畫檔，以及檔頭寫了 `到期: YYYY-MM-DD` 的檔，每個檔只讀前 4 KB。跳過開頭是點的資料夾和 `備份`、`歸檔`、`node_modules`、`__pycache__`、`out` 與該專案 `skipDirs` 列的資料夾，一個專案最多看 3000 個 `.md`。

寫：

- 只有 `todo_core.py index` 寫一個檔：設定資料夾裡的 `todo_index.json`。
- TODO、session_log、計畫檔、有效期檔都只讀。檔頭的到期日過了，開場清單只提醒，不移動、不修改任何檔。
- mod 不寫任何檔，只讀設定檔與 `todo_index.json`。

## 畫面與指令

- 開場清單：所在專案的條目照「誰要做」分組，接著是進行中的 goal 計畫（併入計畫的條目只列在計畫底下，不在專案裡重複列）、3 天內到期或已過期的有效期檔、其他專案的條數與快到期的、格式問題。超過 10,000 字元會截斷並註明。
- `/todo`：列未勾選的條目；`/todo <專案名>` 只列那個專案。
- `/todo pane`：開側欄。側欄頂端按 1～4 換版面（先按 ctrl+x tab 把鍵盤交給側欄），也可以打 `/todo view 2`。
  1. 你要做的：待你決定、你（兩組底下再依專案分小組、縮排）、下一步、goal 進度、等外部（只列條數與 7 天內到期的）、Claude（各專案條數，只展開 7 天內到期的）。
  2. 各專案：每個專案全部展開，最後一組是併進 goal 計畫的條目。
  3. 照期限：已過期、7 天內、之後。
  4. goal 逐步：每份計畫各節的步驟。
  - 設定檔的 `views` 可以只開其中幾個，例如 `["mine", "goal"]`，按鍵照設定順序重編。沒開「各專案」時，「你要做的」裡的等外部與 Claude 改成全展開，一樣依專案分小組。
- `/todo goal`：文字列出 goal 計畫進度。
- `/todo band`：收起或打開輸入框上方的下一步。

還沒有設定檔或 index 時，側欄只顯示一行提示，`/todo` 也只回這行提示。

## TODO 第一行格式

```
- [ ] [誰] 文字（期限 MM-DD）（計畫 檔名）（建 MM-DD）（改 MM-DD）
```

- `[誰]` 只能是 `你`、`你決定`、`Claude`、`等外部`。`你決定` 在畫面上叫「待你決定」，排最前面。標籤不合法的條目照樣列出，歸「未分類」，`lint` 會報。
- `（建 MM-DD）` 必填，開場清單靠它把放超過 14 天的條目標成「待驗現況」；其他欄位可以省略。有寫的話順序固定：期限、計畫、建、改。年份不用寫，期限可以在未來，建立日與修改日不會在未來。
- 文字扣掉欄位括號，60 字以內。細節寫在底下的子項；子項不放 `[誰]` 標籤，要另外拍板的事另開一條。
- 只看頂層的 `- [ ]`；勾掉的、程式碼區塊裡的不算。

例子：

```
- [ ] [等外部] 等王小明回覆問卷第三題要不要改（期限 11-05）（建 10-20）
- [ ] [Claude] 照計畫跑第二章文獻整理（計畫 計畫_第二章.md）（建 10-20）（改 10-22）
  - 第一節已讀完，剩第二、三節
```

`lint` 會報的問題：標籤不合法、缺少標籤、欄位重複、欄位括號格式不對、欄位順序不對、第一行太長、建立日解析不了、計畫檔找不到、子項上面沒有母條目、子項不放標籤、控制字元（例如 Tab，或路徑裡的 `\t` 被轉成 Tab）、讀不到。

手動檢查：

```
python3 scripts/todo_core.py lint                 # 檢查設定檔列的全部 TODO
python3 scripts/todo_core.py lint path/to/TODO.md # 只檢查指定的檔
python3 scripts/todo_core.py render               # 印開場清單
```

有問題時 `lint` 結束碼是 1。

## goal 計畫檔

TODO 條目的 `（計畫 檔名）` 欄位，或文字裡出現符合 `planGlob` 的檔名，就去專案資料夾找那份計畫。計畫檔內文要有 `/goal`，而且還有沒勾的步驟，才算進行中：

- `# 計畫：標題` 是標題。
- 每個 `## ` 是一節，節內的 `- [ ]`／`- [x]` 是步驟。
- 檔頭的 `到期: YYYY-MM-DD` 是期限；沒寫的話取引用它的條目裡最近的期限。

條目文字同時有「併入」和「goal」（例如「（併入 第二章 goal 計畫）」），側欄與開場清單都會把它從專案清單拿掉，改列在標題對得上的那份計畫底下。

## 什麼情況下不會動

- `--bare`、`--safe-mode`、設定裡 `disableAllHooks: true`：plugin 的 hook 與 mod 都不跑，開場清單、格式檢查、側欄都沒有。要看清單時手動跑上面的指令。
- 找不到 Python 3.8 以上、Windows 沒有 Git Bash：command hook 跳過或失敗，不擋 session。

## 安全

- mod 在 Claude Code 的行程內執行，不受沙箱限制。這個 mod 只讀設定資料夾裡的兩個檔（`todo.config.json`、`todo_index.json`），讀的環境變數只有 `CLAUDE_CONFIG_DIR`、`HOME`、`USERPROFILE`、`WSL_DISTRO_NAME`，不寫檔、不連網、不開行程。`claude plugin validate ./todo` 會列出它實際呼叫的 API，可以自己核對。
- Python 腳本照一般 command hook 的權限執行，讀寫範圍見上一節。

## 開發

```
python3 tests/test_todo_core.py    # Python 端
claude plugin test ./todo           # mod 畫面
claude plugin validate --strict ./todo
```
