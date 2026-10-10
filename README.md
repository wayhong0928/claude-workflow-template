# claude-workflow-template

給研究生用的 Claude Code 工作流程設定，裝進你自己的專案資料夾（論文、文獻筆記、報告）就能用。裝好之後：

- **開 session 會接上次的進度**：Claude 開場先讀上次的紀錄，用一兩句話告訴你做到哪、還剩什麼。
- **派 subagent 前要先寫清楚**：Claude 要把工作交給 subagent 時，得先載入派工模板，寫明目標、驗收條件和回報格式；沒載入就會被擋下。
- **做完的東西由另一個 agent 驗收**：重要的產出（論文段落、對外發布的內容）交給沒參與製作的 `verifier` 檢查，做的人不驗自己的活。
- **幾個常見錯誤有自動把關**：檔案裡混進看不見的控制字元會被擋下；對話太長時會提醒你先存進度。

幾個名詞：**hook** 是 Claude Code 在特定時間點（開場、使用工具前、回合結束）自動執行的小程式，可以補充資訊給 Claude，也可以擋下動作。**subagent** 是 Claude 另外開的一個助手，在自己的對話裡做完一件事再回報。**context** 是 Claude 目前這段對話記得的內容，太長時要用 `/clear` 清掉重來。

介紹頁：<https://wayhong0928.github.io/claude-workflow-template/>

## 適合誰

- 用 Claude Code（終端機版），專案會跨很多個 session。
- 專案以寫作和研究為主：論文、文獻筆記、報告。程式專案也能用，但純寫程式的話，[Superpowers](https://github.com/obra/superpowers) 這類套件比較合適（差異見 [docs/vs-superpowers.md](docs/vs-superpowers.md)）。
- 主要在 Windows 上測過。hook 是 Python，各平台都能跑；session_log 的開場注入用 PowerShell，macOS／Linux 要另外裝 PowerShell 7。

不需要會 Git。

## 安裝前：確認環境

| 工具 | 用來做什麼 | 必要嗎 | 怎麼檢查 | 沒有的話 |
|---|---|---|---|---|
| Claude Code 2.1.271 以上 | 這套設定就是給它用的 | 必要 | `claude --version` | 照[官方說明](https://code.claude.com/docs/en/setup)安裝。更新：原生安裝用 `claude update`，WinGet 裝的用 `winget upgrade Anthropic.ClaudeCode`，Homebrew 裝的用 `brew upgrade claude-code` |
| Python 3.8 以上 | 所有 hook 和安裝程式 | 必要 | `python --version`（Mac 試 `python3 --version`） | Windows：`winget install Python.Python.3.12`；Mac：`brew install python` |
| PowerShell | session_log 的開場注入 | 只有裝 session_log 才要 | Windows 內建；Mac／Linux：`pwsh --version` | Mac：`brew install powershell`；或者不裝 session_log |
| Git | 下載這個 template | 不必要 | `git --version` | 改用下載 ZIP |

Windows 上打 `python` 如果跳出 Microsoft Store，代表還沒裝 Python，那只是系統內建的捷徑。

## 安裝方法一：讓 AI 幫你裝（建議）

在**你的專案資料夾**開 Claude Code 或 Codex（在那個資料夾開終端機，打 `claude` 或 `codex`），把下面整段貼給它。它會先檢查環境、缺什麼先問你要不要裝，每一步都等你同意才做。

用 Codex 裝也可以，但裝好的東西只在 Claude Code 裡有作用。

```text
請幫我把 claude-workflow-template（https://github.com/wayhong0928/claude-workflow-template）裝進目前這個資料夾。每一步先說你要做什麼、要跑什麼指令，等我同意再做。不要自己改我專案裡原本的檔案，所有修改都交給它的 install.py（它會先備份）。

1. 檢查環境，逐項回報「有／沒有」和版本：
   - 作業系統。
   - Claude Code：claude --version，要 2.1.271 以上。
   - Python：依序試 python、python3、py（Windows 才試 py），要 3.8 以上。Windows 上如果跳出 Microsoft Store 或印出 "Python was not found"，算沒有。
   - Git：git --version。
   - 不是 Windows 的話，再查 pwsh --version。
2. 沒有 Python 或 Claude Code 版本太舊：停下來，告訴我怎麼裝或更新（Python：Windows 用 winget install Python.Python.3.12，Mac 用 brew install python；Claude Code：看它是怎麼裝的，原生安裝用 claude update，WinGet 用 winget upgrade Anthropic.ClaudeCode，Homebrew 用 brew upgrade claude-code），問我要不要現在做。我說不要，就到此結束。
3. 沒有 Git：問我要不要裝（Windows：winget install Git.Git；Mac：xcode-select --install）。我說不要也沒關係，下一步改下載 ZIP。
4. 把 template 下載到暫存資料夾，不要放進我的專案。有 Git 就用 git clone --depth 1；沒有就下載 https://github.com/wayhong0928/claude-workflow-template/archive/refs/heads/main.zip 再解壓縮。
5. 問我要不要裝 session_log（每次開 session 自動接上次的進度，會在專案裡多出 session_log.md 和 TODO.md）。給我一句建議：這個資料夾不是 git repo（例如論文資料夾、Obsidian 筆記庫）就建議裝；是程式 repo 的話可以不裝。不是 Windows 又沒有 pwsh 的話，不能裝。
6. 先預演：python <暫存資料夾>/install.py <我的專案資料夾> --dry-run，加上 --session-log 或 --no-session-log。把它列出的動作講給我聽；我同意後，拿掉 --dry-run 正式執行。指令裡的 python 換成第 1 步找到的那個。
7. 在我的專案資料夾跑 python .claude/hooks/tests/run_tests.py，最後一行要是「21/21 通過」（前後數字一樣就是全過）。沒通過就把輸出貼給我，不要自己改 hook。
8. 如果 install.py 說它新建了 CLAUDE.md：一次問我一題，把裡面的【】填完；我答不出來的那一行就刪掉。
9. 刪掉暫存資料夾。回報：裝了什麼、哪些原本就有、備份放在哪、哪一步失敗或被我跳過。最後提醒我關掉 Claude Code，在專案資料夾重新打 claude，再打 /hooks 確認。
```

**AI 做完後你要檢查**：在專案資料夾重新打 `claude`，再打 `/hooks`，看得到 `PreToolUse`、`PostToolUse`、`UserPromptSubmit`、`Stop` 四類（裝了 session_log 會多一個 `SessionStart`）。

## 安裝方法二：自己裝

1. 下載：按這頁上方綠色的 **Code** → **Download ZIP**，解壓縮到任何地方（不要解壓縮到你的專案裡）。會用 Git 的話，`git clone` 也可以。
2. 在解壓縮出來的資料夾打開終端機（Windows：在資料夾空白處按右鍵，選「在終端機中開啟」；Mac：開「終端機」，打 `cd `（後面有空格）再把資料夾拖進視窗、按 Enter），先預演（Windows 範例，路徑換成你的專案；Mac 把 `python` 換成 `python3`）：

   ```
   python install.py "D:\碩論\筆記" --session-log --dry-run
   ```

   它會列出要新增幾個檔案、覆蓋哪些檔案、改哪些設定，不會真的動。不想裝 session_log 就把 `--session-log` 換成 `--no-session-log`；兩個都不寫，它會自己判斷（專案不在 git repo 裡就裝）。
3. 確認沒問題，拿掉 `--dry-run` 再跑一次。
4. 在終端機用 `cd "D:\碩論\筆記"` 切到你的專案資料夾，跑 `python .claude/hooks/tests/run_tests.py`（Mac 一樣換成 `python3`），最後一行要是「21/21 通過」（前後數字一樣就是全過）。
5. 打開專案裡的 `CLAUDE.md`，把【】填完（install.py 有新建它的話）。
6. 在專案資料夾打 `claude`，再打 `/hooks` 確認。

### install.py 會做什麼

- 把 `template/.claude/` 底下的檔案複製到你專案的 `.claude/`。
- 把 hook 設定合併進 `.claude/settings.json`。你原本的設定都保留，只加這幾項。
- 專案沒有 `CLAUDE.md` 才新建一份。裝 session_log 時，在 CLAUDE.md 結尾加一段接力說明，前後有 `<!-- claude-workflow-template:start -->`、`<!-- claude-workflow-template:end -->` 標記。
- 裝 session_log 時，專案沒有 `session_log.md`、`TODO.md` 才各建一份。
- 專案在 git repo 裡時，`.gitignore` 加上 hook 執行時產生的本機狀態檔。

覆蓋或修改前，舊檔會先備份到 `.claude/backup/workflow-template-<時間>/`。重複執行不會重複加設定，所以之後要更新，下載新版再跑一次就好。

### 移除

```
python install.py "D:\碩論\筆記" --uninstall
```

會拿掉 settings.json 裡這個 template 的 hook、`.claude/` 裡它裝的檔案，以及 CLAUDE.md 裡標記的那一段。`CLAUDE.md`、`session_log.md`、`TODO.md` 是你的內容，不會刪。settings.json 原本只有這些 hook 的話，會剩下一個內容是 `{}` 的空檔，可以刪掉；`.claude/backup/` 裡是安裝和移除前的備份，確定不要了也可以刪。

## 裝好之後怎麼用

王小明的碩論文獻筆記放在一個 Obsidian 資料夾，沒有用 Git。

1. 照上面裝好，選擇裝 session_log。CLAUDE.md 這樣填：
   - 這個專案是什麼：「你是王小明的文獻筆記助理。專案目標：每篇讀過的論文都有一份筆記，標出研究問題、方法、主要發現。」
   - 不能違反的規則：「不得修改 `pdf/` 底下的檔案」「引用一律 APA 第七版」。
2. 每次都在筆記資料夾打 `claude`，不然 hook 和 CLAUDE.md 載不到。
3. 開場 Claude 會先說上次做到哪。照常交代工作就好。
4. 一段工作做完，跟 Claude 說「補 log」，它會照格式在 `session_log.md` 最上面加一筆，並更新 `TODO.md`。下次開 session，開場就會看到這一筆。
5. Claude 要派 subagent 時，你會看到它先載入 `dispatch-template`；重要的產出，它會派 `verifier` 驗收後才說完成。

session_log 每筆的格式和寫法見 [template/.claude/session-log-kit/README.md](template/.claude/session-log-kit/README.md)；每個機制在什麼時候發生，見 [docs/how-it-works.md](docs/how-it-works.md)。

## repo 裡有什麼

```
install.py                 安裝與移除
template/                  會被裝進你專案的東西
  .claude/
    hooks/                 四支 hook、一支共用模組、測試
    skills/dispatch-template/  派工 prompt 模板、模型選型表
    agents/verifier.md     驗收用的 subagent
    rules/dispatch-and-verify.md  什麼時候派 subagent、怎麼驗收
    session-log-kit/       session_log 的注入、寫入、歸檔腳本
  hooks-core.json          install.py 合併進 settings.json 的 hook 設定
  hooks-session-log.json   同上，session_log 用
  CLAUDE.md.template       新建 CLAUDE.md 時用
  session_log.md.template、TODO.md.template
docs/
  how-it-works.md          一個 session 照什麼順序發生、要不要裝 session_log、怎麼改成自己的版本
  vs-superpowers.md        跟 Superpowers 的差異
tests/test_install.py      install.py 的測試
index.html                 介紹頁
```

在這個 repo 的資料夾裡開 `claude` 不會啟用任何 hook，東西都放在 `template/` 底下，裝進你的專案才會生效。

## 已知限制

- `rules/` 和 `dispatch-template` 是寫給 Claude 看的規則，它不一定每次都照做；會強制的只有 hook 那幾項。
- hook 全部 fail-open：出錯時一律放行，不會卡住你，但壞掉時也不會有提示。改了 hook 請跑測試。
- `ctrl_char_stop.py` 只檢查得到 transcript 裡有完整路徑的檔案，指令裡用變數組出來的路徑會漏掉。
- session_log 的兩支 `.ps1` 只在 Windows 上跑過；hook 測試在 Windows 和 Linux 都跑過。Mac 還沒測。
- 只支援 Claude Code。Codex 可以幫你執行安裝，但 hook、skill、規則檔都是 Claude Code 的格式。

## 回報問題

裝不起來、hook 誤擋或該擋沒擋，請到 [Issues](https://github.com/wayhong0928/claude-workflow-template/issues) 回報，附上作業系統和 `install.py` 或測試的輸出。

## 同系列

| 資源 | 適合誰 |
|---|---|
| [mis-thesis-guide](https://wayhong0928.github.io/mis-thesis-guide/) | 研究方法與論文寫作的知識庫，查觀念、查判準 |
| [一小時上手](https://wayhong0928.github.io/mis-thesis-guide/pages/ai-quickstart.html) | 只用 ChatGPT、Claude、Gemini 網頁版，想在一小時內建好論文助手（另有 [Claude Code、Codex 版](https://wayhong0928.github.io/mis-thesis-guide/pages/ai-quickstart-agent.html)） |
| [thesis-notes-template](https://github.com/wayhong0928/thesis-notes-template) | 想用 Obsidian 做文獻筆記，要現成的模板和填寫規則 |
| [mis-thesis-skills](https://github.com/wayhong0928/mis-thesis-skills) | 用 Claude Code 或 Codex，想讓 AI 照固定判準檢查題目與寫作 |

## 授權

MIT，見 [LICENSE](LICENSE)。
