# 全新安裝基準測試（2026-10，現行 main）

10/24 出新版前，替現行 main 做的基準測試。把自己當成第一次安裝的新使用者，在乾淨的雲端 Linux 照 README「安裝方法二：自己裝」從零裝一次，再跑測試、檢查裝出來的東西、移除還原，最後列出 README 和實際行為對不上的地方。

- 測試日期：2026-10-23
- 受測版本：`main` @ `9b234a8`（網站加淺色／深色切換；index 與 README 加派工到驗收圖解）
- 這份檔案是唯一的改動，沒有改 repo 裡其他檔案。

## 結論

| 項目 | 結果 |
|---|---|
| `--no-session-log` 安裝（預演＋正式） | 成功 |
| `--session-log` 安裝，沒有 pwsh | 預演和正式安裝都 **exit 1**，沒動任何檔案（錯誤訊息講得很清楚） |
| 照 README 表格裝 PowerShell 7 之後再裝 `--session-log` | 成功 |
| `tests/test_install.py` | 有 pwsh：**48/48**；沒有 pwsh：**30/30**（另外 18 項略過，只印一行 SKIP） |
| 專案裡的 `.claude/hooks/tests/run_tests.py` | 兩個專案都是 **25/25** |
| settings.json 是否為合法 JSON | 兩個都合法 |
| 手動執行 hook 指令（照 settings.json 的 command＋args） | 6 種事件、10 次呼叫都 exit 0，輸出符合預期；`ctrl_char_stop.py` 每次都在 stderr 印 SyntaxWarning |
| 用真的 Claude Code 2.1.309 無頭模式開 session | SessionStart（pwsh）、UserPromptSubmit、PreToolUse:Agent（擋下）、Stop 都有觸發 |
| `--uninstall` 還原 | 移除結果和 README 描述一致，但沒有回到安裝前的狀態（見步驟 5 的差異清單） |
| 發現 | 致命 0、錯誤 2、瑕疵 11 |

## 測試環境

| 項目 | 值 |
|---|---|
| 作業系統 | Ubuntu 24.04.5 LTS（雲端容器，核心 6.18.44；`/proc/version` 沒有 microsoft，不是 WSL） |
| Python | `python3` 3.13.16。這個映像檔另外有 `python` → python3（`/etc/alternatives`），一般全新的 Ubuntu 沒有；「只有 python3」的情況用 PATH 另外模擬（步驟 1-4） |
| Claude Code | 2.1.309（README 要求 2.1.292 以上） |
| Git | 有 |
| PowerShell | 一開始**沒有**；後來照 README 表格連到的 Microsoft 說明裝了 PowerShell 7.6.8 |
| unzip | 有（`/usr/bin/unzip`） |

下文的 `$S` 是暫存資料夾（`/tmp/claude-0/.../scratchpad`），不在任何 git repo 裡。檔案清單快照用一支小腳本 `snap.sh` 列出所有檔案、資料夾和 SHA-256 前 16 碼，安裝前、安裝後、移除後各拍一次再 diff。

## 步驟 1：照「安裝方法二」安裝

### 1-0 下載

README 第 69 行：Download ZIP 或 `git clone`。兩條路都試了：

```bash
cd $S && git clone --depth 1 https://github.com/wayhong0928/claude-workflow-template.git tpl
# → 9b234a8，和 origin/main 相同
curl -sSL -o main.zip https://github.com/wayhong0928/claude-workflow-template/archive/refs/heads/main.zip
python3 -m zipfile -e main.zip . && diff -r claude-workflow-template-main tpl -x .git -q
# → ZIP 內容與 clone 相同
```

之後的指令都在 `$S/tpl` 裡跑（README 第 70 行：在解壓縮出來的資料夾開終端機）。依 README 第 67 行，`python` 換成 `python3`。

### 1-1 `--no-session-log`（新資料夾 `$S/proj-nosl`）

```bash
mkdir $S/proj-nosl                      # 安裝前快照：0 筆
python3 install.py $S/proj-nosl --no-session-log --dry-run
```

```
專案資料夾：$S/proj-nosl
hook 用的 Python 指令：python
（預演）複製檔案到 .claude/：新增 9、覆蓋 0、內容相同略過 0
（預演）.claude/settings.json：新建
（預演）CLAUDE.md：新建（裡面有【】空格要填）

預演結束，沒有動任何檔案。拿掉 --dry-run 再跑一次就會正式安裝。
exit=0
```

預演後快照仍是 0 筆，確實沒動檔案。

```bash
python3 install.py $S/proj-nosl --no-session-log
```

```
專案資料夾：$S/proj-nosl
hook 用的 Python 指令：python
複製檔案到 .claude/：新增 9、覆蓋 0、內容相同略過 0
.claude/settings.json：新建
CLAUDE.md：新建（裡面有【】空格要填）

安裝完成。接下來：
  1. 在專案資料夾跑 python .claude/hooks/tests/run_tests.py ，最後一行要是「25/25 通過」（前後數字一樣就是全過）
  2. 打開 CLAUDE.md，把【】填完（也可以請 Claude 一題一題問你）
  3. 專案裡有不能改的原始資料（PDF、問卷原始檔）的話，再跑一次並加上 --protect 資料夾，見 README「保護原始資料」
  4. 關掉正在跑的 Claude Code，在專案資料夾重新打 claude，再打 /hooks 確認看得到這幾個 hook
exit=0
```

### 1-2 `--session-log`，沒有 pwsh（新資料夾 `$S/proj-sl`）

```bash
mkdir $S/proj-sl                        # 安裝前快照：0 筆
python3 install.py $S/proj-sl --session-log --dry-run
python3 install.py $S/proj-sl --session-log
```

兩次都失敗，完整錯誤（stderr）：

```
沒有完成：session_log 的開場注入要用 PowerShell，這台電腦找不到 powershell 或 pwsh。macOS／Linux 請先裝 PowerShell 7，或改用 --no-session-log。
exit=1
```

失敗後快照仍是 0 筆，沒有留下半套安裝。

順便試了兩個旗標都不給的自動判斷（`$S/proj-auto`，不在 git repo 裡）：

```
session_log：不裝（專案不在 git repo 裡，但這台電腦沒有 PowerShell；要改請加 --session-log 或 --no-session-log）
...
（預演）複製檔案到 .claude/：新增 9、覆蓋 0、內容相同略過 0
exit=0
```

### 1-3 照 README 的說法處理：裝 PowerShell 7

README 第 31 行的「沒有的話」欄：「Linux／WSL：照 Microsoft 的 Linux 安裝說明；或者不裝 session_log」。`--no-session-log` 那條路已在 1-1 跑過，這裡走「裝 PowerShell」。照 Microsoft 的 Ubuntu 說明：

```bash
source /etc/os-release
wget -q https://packages.microsoft.com/config/ubuntu/$VERSION_ID/packages-microsoft-prod.deb
dpkg -i packages-microsoft-prod.deb
apt-get update && apt-get install -y powershell
pwsh --version      # → PowerShell 7.6.8
```

一次就裝好，沒有遇到問題。

### 1-4 `--session-log`，有 pwsh（同一個 `$S/proj-sl`，上一步失敗時沒留下任何檔案）

```bash
python3 install.py $S/proj-sl --session-log --dry-run
```

```
專案資料夾：$S/proj-sl
hook 用的 Python 指令：python；PowerShell 指令：pwsh
（預演）複製檔案到 .claude/：新增 13、覆蓋 0、內容相同略過 0
（預演）.claude/settings.json：新建
（預演）CLAUDE.md：新建（裡面有【】空格要填）
（預演）session_log.md：新建
（預演）TODO.md：新建

預演結束，沒有動任何檔案。拿掉 --dry-run 再跑一次就會正式安裝。
exit=0
```

預演後快照 0 筆。正式安裝：

```
專案資料夾：$S/proj-sl
hook 用的 Python 指令：python；PowerShell 指令：pwsh
複製檔案到 .claude/：新增 13、覆蓋 0、內容相同略過 0
.claude/settings.json：新建
CLAUDE.md：新建（裡面有【】空格要填）
session_log.md：新建
TODO.md：新建

安裝完成。接下來：（4 點，和 1-1 相同）
exit=0
```

### 1-5 補充：只有 `python3`、沒有 `python` 的 PATH

一般全新 Ubuntu 沒有 `python`。用一個拿掉 `python` 的 PATH 再裝一次（`$S/proj-py3`）：

```
hook 用的 Python 指令：python3
  1. 在專案資料夾跑 python3 .claude/hooks/tests/run_tests.py ，最後一行要是「25/25 通過」……
settings.json：5 個 "command": "python3"
```

自動改用 `python3`，安裝完的提示也跟著改，沒問題。

### 1-6 補充：git repo＋`--protect`

`$S/proj-git`：`git init`，裡面有 `pdf/a.pdf`、`問卷原始檔.csv`，再加一個專案外的資料夾 `$S/outside`：

```bash
python3 install.py $S/proj-git --protect pdf --protect "問卷原始檔.csv" --protect $S/outside --dry-run
```

```
session_log：不裝（專案在 git repo 裡，進度可以看 git log；要改請加 --session-log 或 --no-session-log）
...
（預演）保護規則：Edit(/pdf/**)（Claude 不能改這裡的檔案）
（預演）保護規則：Edit(/問卷原始檔.csv)（Claude 不能改這裡的檔案）
（預演）保護規則：Edit(//tmp/claude-0/.../scratchpad/outside/**)（Claude 不能改這裡的檔案）
（預演）.claude/settings.json：新建
（預演）CLAUDE.md：新建（裡面有【】空格要填）
（預演）.gitignore：加上 5 行 hook 狀態檔
```

正式安裝後的 `permissions.deny` 和 README 第 141-146 行寫的格式一致。`.gitignore` 加了 5 行，其中 `.claude/backup/` 不是 hook 狀態檔（見發現 #5）。

## 步驟 2：跑測試

### 2-1 `tests/test_install.py`（README 第 203 行只說它是 install.py 的測試；跑法照檔頭：`python tests/test_install.py`）

裝了 pwsh 之後，在 `$S/tpl` 跑：

```bash
python3 tests/test_install.py
```

```
PASS 空專案安裝成功
PASS hook 檔都在
PASS 規則檔在 .claude/rules
PASS session-log-kit 在 .claude 底下
PASS settings 有 6 個 hook
PASS SessionStart 指到 .claude/session-log-kit
PASS 新建 CLAUDE.md 含接力說明
PASS 建了 session_log.md、TODO.md
PASS 不在 git repo 就不碰 .gitignore
PASS 專案根目錄只多出預期的東西
PASS 裝好的 hook 測試全過
PASS 重跑成功
PASS 重跑後 settings 仍是 6 個 hook
PASS 重跑後 CLAUDE.md 接力說明只有一段
PASS 重跑不改任何檔案、不產生備份
PASS 既有專案安裝成功
PASS 保留使用者的其他設定
PASS 保留使用者自己的 hook
PASS 加了 5 個 hook、沒有 SessionStart
PASS CLAUDE.md 沒被改
PASS 沒建 session_log.md
PASS .gitignore 保留原本、加上狀態檔
PASS settings.json 有備份
PASS 既有 CLAUDE.md 保留原文並加接力說明
PASS 改裝後 6 個 hook
PASS 移除成功
PASS 移除後只剩使用者的 hook
PASS 移除後其他設定還在
PASS 移除後 hook 檔不在
PASS 移除後 CLAUDE.md 回到原文
PASS 移除後 .gitignore 回到原文
PASS settings 格式錯就停
PASS 格式錯時沒動任何檔案
PASS 預演成功且沒建任何檔案
PASS 拒絕裝進 template 本身
PASS CRLF 檔案寫回後仍是 CRLF
PASS 預演有說明會匯入 AGENTS.md
PASS 新建的 CLAUDE.md 第一行是 @AGENTS.md
PASS AGENTS.md 沒被改
PASS 重跑不重複加 @AGENTS.md
PASS 預演列出保護規則且沒改 settings
PASS 資料夾、檔案、專案外路徑各一條規則，原本的 deny 保留在前
PASS permissions 的其他設定保留
PASS 重跑不重複加保護規則
PASS --protect 路徑不存在就停、不動檔案
PASS --protect 整個專案會被拒絕
PASS 移除時保護規則留著
PASS permissions.deny 不是陣列就停

48/48 通過
exit=0
```

為了重現「新使用者還沒裝 pwsh」的情況，用拿掉 pwsh 的 PATH 再跑一次（注意 Ubuntu 的 `/bin` 是 `/usr/bin` 的連結，第一次只拿掉 `/usr/bin` 沒藏住，重做後 `command -v pwsh` 確認找不到）：

```
SKIP 空專案＋session_log（這台電腦沒有 PowerShell）
PASS 既有專案安裝成功
PASS 保留使用者的其他設定
PASS 保留使用者自己的 hook
PASS 加了 5 個 hook、沒有 SessionStart
PASS CLAUDE.md 沒被改
PASS 沒建 session_log.md
PASS .gitignore 保留原本、加上狀態檔
PASS settings.json 有備份
PASS 移除成功
PASS 移除後只剩使用者的 hook
PASS 移除後其他設定還在
PASS 移除後 hook 檔不在
PASS 移除後 CLAUDE.md 回到原文
PASS 移除後 .gitignore 回到原文
PASS settings 格式錯就停
PASS 格式錯時沒動任何檔案
PASS 預演成功且沒建任何檔案
PASS 拒絕裝進 template 本身
PASS 預演有說明會匯入 AGENTS.md
PASS 新建的 CLAUDE.md 第一行是 @AGENTS.md
PASS AGENTS.md 沒被改
PASS 重跑不重複加 @AGENTS.md
PASS 預演列出保護規則且沒改 settings
PASS 資料夾、檔案、專案外路徑各一條規則，原本的 deny 保留在前
PASS permissions 的其他設定保留
PASS 重跑不重複加保護規則
PASS --protect 路徑不存在就停、不動檔案
PASS --protect 整個專案會被拒絕
PASS 移除時保護規則留著
PASS permissions.deny 不是陣列就停

30/30 通過
exit=0
```

18 項略過（空專案＋session_log 那 15 項、改裝成 6 個 hook 那 2 項、CRLF 那 1 項），最後一行仍是「30/30 通過」（見發現 #12）。

### 2-2 專案裡的 `run_tests.py`（README 第 78 行）

```bash
cd $S/proj-nosl && python .claude/hooks/tests/run_tests.py
cd $S/proj-sl   && python .claude/hooks/tests/run_tests.py
```

兩個專案的輸出相同（只差「受測 hooks」那行的路徑）：

```
PASS dispatch_gate: 未叫用 dispatch-template -> 擋
PASS dispatch_gate: 已叫用 -> 放
PASS dispatch_gate: fork 免檢 -> 放
PASS dispatch_gate: 不是 Agent 工具 -> 放
PASS dispatch_gate: 叫用後發生 compact -> 擋
PASS dispatch_gate: compact 後重新叫用 -> 放
PASS skill_gate_flag_writer: 裸名稱 -> 寫 flag
PASS skill_gate_flag_writer: plugin:skill 格式 -> 用裸名稱寫 flag
PASS skill_gate_flag_writer: 未受管制的 skill -> 不寫
PASS skill_gate_flag_writer: 使用者打 /dispatch-template -> 寫 flag
PASS skill_gate_flag_writer: 使用者打 /plugin:dispatch-template -> 用裸名稱寫 flag
PASS 串接: Skill 叫用後 dispatch_gate 放行
PASS context_guard: 5 萬 -> 不提醒
PASS context_guard: 16 萬 -> 提醒一次
PASS context_guard: 同一級再來 -> 不重複提醒
PASS context_guard: 跨到下一級 -> 再提醒
PASS context_guard: 只看主對話、不看 sidechain -> 不提醒
PASS ctrl_char_stop: .md 含 \x08 -> 擋
PASS ctrl_char_stop: 狀態檔寫在 hook 旁邊、不在家目錄
PASS ctrl_char_stop: 正常中文 -> 放
PASS ctrl_char_stop: CRLF 換行 -> 放
PASS ctrl_char_stop: Bash 指令裡的絕對路徑 -> 擋
PASS ctrl_char_stop: 引號包住、含空白與中文的路徑 -> 擋
PASS 隔離: 擋下事件的 log 寫進沙箱
PASS 隔離: 原始 hooks 資料夾的狀態檔與 log 前後一致（SHA-256 與 mtime）

受測 hooks：$S/proj-nosl/.claude/hooks

25/25 通過
exit=0
```

改用 `python3` 跑結果一樣（25/25）。跑完後的快照和安裝後的完全相同，測試沒在專案裡留下任何檔案。

### 測試合計

| 測試 | 通過／共 |
|---|---|
| `tests/test_install.py`（有 pwsh） | 48/48 |
| `tests/test_install.py`（沒有 pwsh） | 30/30（另外 18 項略過） |
| `run_tests.py`（proj-nosl） | 25/25 |
| `run_tests.py`（proj-sl） | 25/25 |
| **合計（有 pwsh 的完整一輪：48＋25＋25）** | **98/98** |

## 步驟 3：裝好後檢查

### 3-1 產生了哪些檔案

`--no-session-log`（11 個檔案）：

```
.claude/agents/verifier.md
.claude/hooks/context_guard.py
.claude/hooks/ctrl_char_stop.py
.claude/hooks/dispatch_gate.py
.claude/hooks/gate_flags.py
.claude/hooks/skill_gate_flag_writer.py
.claude/hooks/tests/run_tests.py
.claude/rules/dispatch-and-verify.md
.claude/settings.json
.claude/skills/dispatch-template/SKILL.md
CLAUDE.md
```

`--session-log`（17 個檔案）＝上面 11 個，加上：

```
.claude/session-log-kit/README.md
.claude/session-log-kit/add_session_log.py
.claude/session-log-kit/archive_session_log.ps1
.claude/session-log-kit/sessionstart_log.ps1
TODO.md
session_log.md
```

複製進去的檔案 SHA-256 和 template 裡的相同。兩個專案都不在 git repo 裡，所以都沒有 `.gitignore`、也沒有 `.claude/backup/`（沒有東西需要備份）。和 README 第 84-88 行的描述一致。

### 3-2 settings.json 是不是合法 JSON

```bash
python3 -m json.tool $S/proj-sl/.claude/settings.json   >/dev/null && echo JSON-OK-sl     # → JSON-OK-sl
python3 -m json.tool $S/proj-nosl/.claude/settings.json >/dev/null && echo JSON-OK-nosl   # → JSON-OK-nosl
```

兩個都合法。`proj-nosl` 的內容等於 `proj-sl` 拿掉 `SessionStart`。`proj-sl` 有 6 個事件：`PreToolUse`（matcher `Agent`）、`PostToolUse`（`Skill`）、`UserPromptExpansion`（`(^|:)dispatch-template$`）、`UserPromptSubmit`、`Stop`、`SessionStart`。前 5 個都是 `"command": "python"`＋`"args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/<腳本>.py"]`；SessionStart 是 `"command": "pwsh"`＋`["-NoProfile","-ExecutionPolicy","Bypass","-File","${CLAUDE_PROJECT_DIR}/.claude/session-log-kit/sessionstart_log.ps1"]`。

### 3-3 照設定裡的實際指令手動跑 hook

寫了一支小腳本（放在專案外的 `$S/scripts/run_hooks.py`）：讀 settings.json，每個 hook 的 argv 用 `[command] + args` 組，`${CLAUDE_PROJECT_DIR}` 換成專案路徑，也設成環境變數，工作目錄設在專案，stdin 餵假的 hook 輸入 JSON，timeout 照設定的 10 秒。假的 transcript 也一起產生。

| 事件 | 假輸入 | 預期 | exit | 實際 stdout |
|---|---|---|---|---|
| PreToolUse | `tool_name: Agent`、`subagent_type: general-purpose`，還沒載入 skill | 擋 | 0 | 合法 JSON，`permissionDecision: "deny"`，理由是「這次要派 general-purpose subagent，但本 session 還沒叫用過 dispatch-template skill……」 |
| PostToolUse | `tool_name: Skill`、`tool_input.skill: dispatch-template` | 寫 flag | 0 | 空；產生 `skill_gate_flags/fake-session-1__dispatch-template.flag` |
| UserPromptExpansion | `command_name: dispatch-template`（session 2） | 寫 flag | 0 | 空；產生 `fake-session-2__dispatch-template.flag` |
| UserPromptSubmit | transcript 最後一筆 usage 合計 5 萬 | 不提醒 | 0 | 空 |
| UserPromptSubmit | transcript 最後一筆 usage 合計 16 萬 | 提醒 | 0 | 合法 JSON，`additionalContext: "[context_guard] 目前主對話 context 約 160k tokens（門檻 150k）……"` |
| Stop | 本回合用 Write 寫了含 `\x08` 的 .md | 擋 | 0 | 合法 JSON，`decision: "block"`，指出「第 2 行 U+0008」 |
| Stop | 本回合用 Write 寫了正常中文 .md | 放 | 0 | 空 |
| SessionStart（pwsh） | `source: startup`，session_log.md 是剛裝好的範本 | 注入 | 0 | 合法 JSON，`additionalContext` 是範本全文（0.93 秒） |
| PreToolUse | 同第 1 列，flag 已寫入 | 放 | 0 | 空 |
| PreToolUse | session 2 派 `Explore`（使用者打過 /dispatch-template） | 放 | 0 | 空 |

10 次呼叫的行為都符合預期。唯一的異狀：`ctrl_char_stop.py` 每次執行都在 stderr 印出（Python 3.13）：

```
$S/proj-nosl/.claude/hooks/ctrl_char_stop.py:11: SyntaxWarning: invalid escape sequence '\.'
  Windows 路徑（C:\...、C:/...、/c/...）與 POSIX 絕對路徑（/home/...、/Users/...、/mnt/c/...）都認；
```

用 `python3 -W error` 編譯 template 裡所有 .py，只有這支報 `SyntaxError: invalid escape sequence '\.'`（見發現 #3）。

### 3-4 session_log 套件在 Linux 上實際跑（複製一份 `proj-sl` 到 `$S/flow` 來試）

- `add_session_log.py`（CLAUDE.md 接力說明裡的指令）：連續插入 5 筆（09-01、09-05、10-01、10-20、10-22），每次都印「已插入：…（標題 n→n+1）」。故意餵一筆標題沒有 `|` 的，回「不寫入：第一行不是「## YYYY-MM-DD | 主題」…」，exit 1。
- `sessionstart_log.ps1`：注入最新 1 筆全文，加上 10-20、10-01 兩筆的標題與「下一步」，符合 session-log-kit README 的描述。
- 找 `notes/session_log.md` 的備援：腳本裡寫的是 `notes\session_log.md`（反斜線），在 Linux 的 pwsh 7 上一樣找得到。
- `archive_session_log.ps1`（session-log-kit README 的指令，`powershell` 換成 `pwsh`）：

  ```
  已歸檔 2 筆（早於 2026-10-16）至 $S/flow/session_log_archive.md；log 保留 3 筆。
  exit=0
  ```

  內容正確，但 `session_log.md` 從 LF 變成 CRLF，`session_log_archive.md` 也是 CRLF（見發現 #11）。之後 `add_session_log.py` 會沿用 CRLF，不會壞。

### 3-5 用真的 Claude Code 確認 hook 會觸發

`/hooks` 是互動式指令，在這裡沒辦法打。改在 `$S/flow` 用 Claude Code 2.1.309 的無頭模式開兩個 session（`--include-hook-events --output-format stream-json`，模型 haiku）：

1. `claude -p "只回覆 ok 兩個字，不要使用任何工具"`：`SessionStart:startup`（pwsh）exit 0、成功注入 session_log；`UserPromptSubmit` exit 0；`Stop` exit 0，**hook 輸出裡就是那行 SyntaxWarning**。
2. `claude -p "測試用：直接呼叫 Agent 工具一次……被 hook 擋下就停止"`：`PreToolUse:Agent` exit 0，回傳 deny，Claude 收到的 tool_result 是 `PreToolUse:Agent hook error: 這次要派 general-purpose subagent，但本 session 還沒叫用過 dispatch-template skill……`，`gate_trial.log` 多了一行 deny 紀錄。

所以 `command`＋`args` 這種寫法和 `${CLAUDE_PROJECT_DIR}` 展開，在 Linux 的 Claude Code 上都有效。PostToolUse:Skill 和 UserPromptExpansion 這次沒有在真的 Claude Code 裡觸發，只有手動跑過（3-3）。

### 3-6 `--uninstall` 能不能還原

先讓 3-3 的 hook 產生狀態檔（`__pycache__/`、`skill_gate_flags/` 兩個 flag、`context_guard_state.json`、`ctrl_char_stop_state.json`、`gate_trial.log`），再移除。

```bash
python3 install.py $S/proj-nosl --uninstall --dry-run   # 列出 2 個動作，快照不變
python3 install.py $S/proj-nosl --uninstall
```

```
專案資料夾：$S/proj-nosl
.claude/settings.json：拿掉這個 template 的 hook，其他設定保留
移除 .claude/ 裡這個 template 的檔案 9 個（先備份）

移除完成。CLAUDE.md、session_log.md、TODO.md 是你的內容，沒有刪；不需要的話自己刪。
備份在：.claude/backup/workflow-template-20261023-024416/（確定不要了可以整個刪掉）
exit=0
```

`proj-sl` 一樣，多一行「CLAUDE.md：拿掉接力說明那段，其他內容不動」，移除 13 個檔案。

**移除後和安裝前（空資料夾）比對，多出來的東西：**

| 專案 | 多出來的 | 內容 |
|---|---|---|
| 兩個都有 | `.claude/settings.json` | `{}` |
| 兩個都有 | `.claude/backup/workflow-template-<時間>/` | 移除前的備份（nosl 10 個檔、sl 15 個檔） |
| 兩個都有 | `CLAUDE.md` | 沒填過的範本（還有【】）；sl 的接力說明已拿掉，和 nosl 的 SHA-256 相同 |
| proj-sl | `session_log.md`、`TODO.md` | 沒動過的範本 |

hook 狀態檔全部刪掉了（沒有備份），`.claude/hooks/` 等空資料夾也刪了。這和 README 第 98 行的描述一致。要回到真正的空資料夾，要自己刪 `.claude/` 和 `CLAUDE.md`（session_log 版再刪兩個 .md）。

**在 git repo 裡移除（`$S/proj-git`，安裝前沒有 .gitignore）：**

```
.gitignore：拿掉安裝時加的幾行
settings.json 的 permissions.deny（保護規則）沒有動，原始資料繼續受保護；不需要的話自己刪。
```

- 留下一個 1 byte 的 `.gitignore`（只有換行），安裝前沒有這個檔（發現 #7）。
- `.gitignore` 裡的 `.claude/backup/` 被拿掉了，但備份資料夾還在，`git status` 顯示 `?? .claude/`（發現 #2）。

**在 git repo 裡移除（`$S/proj-git2`，安裝前已有 `.gitignore: node_modules/` 和 `.claude/settings.json: {"env":{"A":"1"}}`）：**

- `.gitignore` 回到原文。
- `settings.json` 內容一樣，但從一行被改成縮排 2 格的格式，SHA-256 不同（發現 #10）。
- 安裝時的備份只有 `settings.json`，修改 `.gitignore` 前沒有備份（發現 #6）。
- `git status --untracked-files=all` 列出兩次的備份共 10 個以上檔案，都可能被 `git add .` 收進去（發現 #2）。

## 步驟 4：README 和實際行為對不上的地方

| README 行號 | README 怎麼寫 | 實際發生什麼 | 對應發現 |
|---|---|---|---|
| 73、76 | 範例：`python install.py "D:\碩論\筆記" --session-log --dry-run`，「它會列出要新增幾個檔案、覆蓋哪些檔案、改哪些設定」 | Linux 沒有 pwsh 時，預演就 exit 1：「沒有完成：session_log 的開場注入要用 PowerShell……」。方法二的步驟沒提這件事，只有第 21、31 行的環境說明有提 | #1 |
| 76 | 「兩個都不寫，它會自己判斷（專案不在 git repo 裡就裝）」 | 不在 git repo 但沒有 PowerShell 時不裝：「session_log：不裝（專案不在 git repo 裡，但這台電腦沒有 PowerShell……）」 | #4 |
| 88 | 「專案在 git repo 裡時，`.gitignore` 加上 hook 執行時產生的本機狀態檔」 | 加的 5 行裡有 `.claude/backup/`（安裝備份），不是 hook 狀態檔；install.py 的訊息也寫「加上 5 行 hook 狀態檔」 | #5 |
| 90 | 「覆蓋或修改前，舊檔會先備份到 `.claude/backup/workflow-template-<時間>/`」 | 修改既有的 `.gitignore` 前沒有備份，備份資料夾裡只有 settings.json | #6 |
| 98 | 移除會拿掉 hook、它裝的檔案、CLAUDE.md 那一段；settings.json 剩 `{}`；`.claude/backup/` 可以刪 | 描述的部分都對。沒寫到的：(a) git repo 裡 `.gitignore` 的 `.claude/backup/` 也拿掉，備份變成未追蹤檔；(b) 原本沒有 `.gitignore` 的會留下一個空的；(c) `gate_trial.log` 等狀態檔直接刪除、不備份；(d) settings.json 會被重新排版 | #2、#7、#8、#10 |
| 203 | `tests/test_install.py      install.py 的測試` | README 沒寫怎麼跑（檔頭寫 `python tests/test_install.py`）。沒有 pwsh 時 18 項略過，最後一行仍是「30/30 通過」 | #12 |
| 21、217 | 「session_log 的兩支 `.ps1` 只在 Windows PowerShell 5.1 上跑過」 | 這次在 Ubuntu 24.04＋PowerShell 7.6.8 上跑過：開場注入、`notes/` 備援、歸檔都能用，但歸檔會把檔案改成 CRLF。這句話不算錯，新版可以更新測試範圍 | #11 |
| 63、80 | 打 `/hooks` 看得到 5 類（＋SessionStart） | 沒辦法互動確認；settings.json 確實是這 6 類，無頭模式也看到 SessionStart、UserPromptSubmit、PreToolUse、Stop 觸發 | （未驗證，非發現） |

README 寫的其他步驟（第 67、69、70、77、78、84-87、141-146 行）實際跑起來都和描述一致。

## 發現清單

嚴重度：**致命**＝裝不起來或會弄丟使用者資料；**錯誤**＝照文件做會失敗，或結果和文件說的不同，而且有實際後果；**瑕疵**＝不影響主要功能的小問題、文件不精確、測試缺口。

| # | 檔案:行號 | 問題 | 嚴重度 | 建議修法 |
|---|---|---|---|---|
| 1 | `README.md:73`、`README.md:76` | 方法二唯一的範例帶 `--session-log`。macOS、Linux、WSL 沒有 pwsh 的新使用者照抄，預演就 exit 1。install.py 的錯誤訊息清楚、也沒動檔案，但 README 步驟沒先講 | 錯誤 | 第 76 行加一句「macOS、Linux、WSL 沒有 `pwsh` 的話，用 `--no-session-log`，或先照上面表格裝 PowerShell 7」；或範例改成 `--no-session-log`，再說明 `--session-log` 的條件。README.en.md:75、78 同步改 |
| 2 | `install.py:512-519`（`README.md:98`） | git repo 裡移除時，`.gitignore` 拿掉 `.claude/backup/`，但移除程序剛在那裡建了備份（安裝時的備份也還在）。備份變成未追蹤檔，`git add .` 會把舊的 settings.json、hook 副本 commit 進去 | 錯誤 | 移除時如果 `.claude/backup/` 還在，就保留 `.gitignore` 裡的 `.claude/backup/` 和標題行（只拿掉 hook 狀態那 4 行）；README 第 98 行補一句 |
| 3 | `template/.claude/hooks/ctrl_char_stop.py:11` | docstring 裡的 `C:\...` 是無效跳脫序列，Python 3.12 以上每次執行都在 stderr 印 SyntaxWarning；真的 Claude Code 的 Stop hook 輸出裡就看得到。Python 未來版本會改成 SyntaxError，到時這支 hook 會失效，而且因為 fail-open 不會有提示。`run_tests.py` 抓不到 | 瑕疵 | 改成 `C:\\...`，或整段 docstring 用 `r"""`；`run_tests.py` 加一項「用 `-W error` 編譯每支 hook」 |
| 4 | `README.md:76` | 「兩個都不寫……專案不在 git repo 裡就裝」，漏了「而且有 PowerShell」 | 瑕疵 | 改成「專案不在 git repo 裡、而且找得到 PowerShell 就裝」 |
| 5 | `README.md:88`、`install.py:433` | `.gitignore` 加的 5 行包含 `.claude/backup/`，README 和安裝訊息都只說「hook 狀態檔」 | 瑕疵 | README 改成「hook 產生的本機狀態檔和安裝備份資料夾」；install.py 第 433 行的訊息同步改（GITIGNORE_HEADER 已經這樣寫了） |
| 6 | `install.py:427-441`（`README.md:90`） | 修改既有的 `.gitignore` 前沒有備份，和 README「覆蓋或修改前，舊檔會先備份」不符。只是附加幾行，風險低 | 瑕疵 | 寫入前呼叫 `plan.backup(gi)`（`gi.exists()` 時）；或 README 註明 `.gitignore` 只附加不備份 |
| 7 | `install.py:512-519` | 原本沒有 `.gitignore` 的 git 專案，移除後留下一個只有換行的 `.gitignore` | 瑕疵 | `kept` 沒有非空白行時直接刪檔，不寫回 `"\n"` |
| 8 | `install.py:491-494`（`README.md:98`） | 移除時把 `gate_trial.log` 等狀態檔直接刪掉、不備份。`gate_trial.log` 是設計來讓人工填 `verdict`（該擋／誤擋）的檢討紀錄，填過的內容會一起消失；README 沒提 | 瑕疵 | `gate_trial.log` 刪除前先 `plan.backup()`（其他狀態檔可以照舊直接刪）；README 第 98 行補一句 |
| 9 | `install.py:502-510`、`README.md:98` | 全新專案移除後，留下沒填過的範本 `CLAUDE.md`（有【】）、`session_log.md`、`TODO.md`。之後在這個資料夾開 claude，還是會載入那份佔位用的 CLAUDE.md。README 說「是你的內容，不會刪」，但這三份是 install.py 建的，使用者沒改過 | 瑕疵 | 移除時如果內容和範本（去掉接力說明後）位元組相同，就刪掉並說明；有改過才保留 |
| 10 | `install.py:476-480`、`install.py:244-245` | 移除時一律用 `indent=2` 重寫 settings.json，使用者原本的排版（例如一行）會被改掉，內容相同但檔案不同，會出現在 git diff 裡 | 瑕疵 | 拿掉 hook 後如果和安裝前的備份語意相同，就直接還原備份那份；或 README 註明會重新排版 |
| 11 | `template/.claude/session-log-kit/archive_session_log.ps1:51-58`、`:69` | 歸檔一律用 `` `r`n `` 寫檔，在 macOS／Linux 上會把 LF 的 `session_log.md` 改成 CRLF，新建的 `session_log_archive.md` 也是 CRLF | 瑕疵 | 照原檔換行寫回：讀檔時偵測有沒有 `\r\n`，沒有就用 `` `n ``（`add_session_log.py` 已經這樣處理） |
| 12 | `tests/test_install.py:96`、`:223`（`README.md:203`） | 沒有 pwsh 時，18 項 session_log 相關檢查只印一行 SKIP、不算進總數，最後一行是「30/30 通過」；「前後數字一樣就是全過」的判讀看不出少測了 18 項。README 也沒寫怎麼跑這支測試 | 瑕疵 | 總結行改成「30/30 通過（略過 18 項：沒有 PowerShell）」；README 第 203 行補跑法 `python tests/test_install.py` |
| 13 | `template/.claude/hooks/tests/run_tests.py` | 25 項只涵蓋 4 支 Python hook；`add_session_log.py`、`sessionstart_log.ps1`、`archive_session_log.ps1` 都沒有自動測試，所以 #11 這類問題測不出來 | 瑕疵 | 加 session-log-kit 的測試：`add_session_log.py` 的插入與擋格式；有 pwsh／powershell 時跑兩支 .ps1，檢查輸出是合法 JSON、換行沒被改 |

**合計：致命 0、錯誤 2、瑕疵 11。**

## 給 10/24 新版的建議

1. 新版在乾淨環境從零裝時，至少重跑這份的 1-1、1-2、1-4、3-3、3-6，加上「有 git repo」的移除比對。重點放在 #1、#2 修好之後的行為。
2. 測試範圍可以更新：Ubuntu 24.04（非 WSL）＋Python 3.13＋PowerShell 7.6.8 上，hook、安裝程式、兩支 .ps1 都跑過（README 第 21、217 行，session-log-kit README 第 61 行）。
3. 這次沒驗證的：互動式 `/hooks` 畫面；PostToolUse:Skill 和 UserPromptExpansion 在真的 Claude Code 裡觸發（只手動跑過）；macOS；只有 Python 3.8 的環境。
