# 更新紀錄

## 1.0.0（workflow-kit）、0.8.0（todo）

測試過的 Claude Code 版本：2.1.310（Windows 11）。Python 測試另在 WSL Ubuntu（Python 3.12）跑過。macOS 沒測過。

### 新的裝法

- 改成 plugin 裝法為主。同一個 marketplace 有兩個 plugin：`workflow-kit`（`.claude-plugin/plugin.json`）和選用的 `todo`（`todo/.claude-plugin/plugin.json`）。
- `workflow-kit` 帶 7 個 hook（`plugin/hooks.workflow.json`）、`dispatch-template` 與 `setup` 兩個 skill、`verifier` agent。
- `/workflow-kit:setup`（`plugin/skills/setup/SKILL.md`）一次問一題，建 CLAUDE.md、session_log.md、TODO.md 與規則檔。要上鎖的資料夾先列出來，你同意才寫進 `permissions.deny`；狀態列只印出設定片段。
- `install.py` 改成備用裝法。專案已啟用 plugin 時會停下來說明，免得兩邊的 hook 各跑一次。
- 新增 `--todo` 旗標。repo 路線也能用 TODO 開場清單與格式檢查（`template/hooks-todo.json`），腳本從 `todo/scripts/` 複製。

### hook 與規則

- 新增 `compact_flag_reset.py`（PostCompact）。對話壓縮後會刪掉 dispatch-template 的載入紀錄，下次派工前要重新載入。
- hook 的狀態檔位置統一由 `hook_state.py` 決定。plugin 版寫進 `CLAUDE_PLUGIN_DATA` 底下、依專案分開的資料夾，不同專案不會互蓋。
- session_log 的開場注入與歸檔改成 Python（`sessionstart_log.py`、`archive_session_log.py`），不再需要 PowerShell。重裝時會移除舊的 `.ps1`。
- `add_session_log.py` 的輸出改成 UTF-8。「下一步」寫到使用者要做的事時，會提醒你把那幾行也寫進 TODO.md。
- `template/TODO.md.template` 換成 v3 第一行格式。日期欄留 `MM-DD` 佔位，填上日期後 `todo_core.py lint` 零錯誤。
- 規則檔、dispatch-template、verifier 依外部審查（C2 22 條、C3 13 條）修正，逐條對照列在 PR 說明。

### todo plugin（0.8.0）

- `todo_core.py` 讀各專案的 TODO.md、session_log 最新一筆的下一步、goal 計畫檔，開場時當場印出清單，也寫成 `todo_index.json` 給 `/todo` 和側欄讀。
- `todo_lint.py` 改到 TODO 時檢查第一行格式，只警告、不擋。
- 側欄 mod（`todo/hooks/register.tsx`）只讀 index 畫畫面。專案清單改由 `todo.config.json` 設定，沒有設定檔時只顯示提示。
- 開場清單多一區「有效期檔案」，列出檔頭 `到期` 在 3 天內的檔，不會搬動任何檔。

### 文件與網站

- README、README.en.md、index.html 的安裝段換成同一段 prompt，另加「公司電腦擋外部套件來源時」與「怎麼更新」兩節。
- 新增 `docs/conventions.md`，寫計畫檔、有效期檔、`out/` 怎麼命名、放哪。
- 新增圖解：TODO 資料流（圖 5）、檔案生命週期（圖 6）、plugin 帶了什麼（圖 8），每張都有寬版與窄版。顏色定義在 `assets/diagram.css`。
- `docs/how-it-works.md` 加「TODO 清單怎麼產生」「plugin 帶了什麼、沒帶什麼」兩節。

## 下一版候選

- 沒有 `todo.config.json` 時，開場提示寫的是 `/workflow-kit:setup`，用 `install.py --todo` 裝的人沒有這個指令。提示要依裝法換字。
- `todo_lint.py` 的警告叫人去看「todo plugin 的 README」，repo 路線也該指得到。
- macOS 實機測試。
- 兩個 plugin 找 Python 的方式不同（`workflow-kit` 用 `userConfig.python`，`todo` 依序試 `python3`、`python`、`py`），要不要統一。
