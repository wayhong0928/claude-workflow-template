# 新版範圍研究：Claude Code 官方變動對照（2026-10）

10/24 規劃新版前的研究筆記。只研究、不改範本：這份檔案是這個分支唯一的改動。

- 研究日期：2026-10-23
- 受測範本：`main` @ `9b234a8`
- 官方資料：2026-10-23 從 `https://code.claude.com/docs/en/<頁面>.md` 抓的原文，以及官方 [CHANGELOG.md](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md)
- 引文規則：每點附官方網址和一句逐字原文。原文裡的 Markdown 超連結只保留連結文字，其他字不動。查不到的就寫「查不到」。

## 結論先講

| 分類 | 項數 |
|---|---|
| (a) 範本用到、官方已改名／棄用／改了行為 | 6 |
| (b) 官方新功能，評估要不要放進範本 | 9 |
| (c) 範本自己做、官方有內建可取代（含評估後不取代的） | 6 |
| 新版範圍：必改 | 4 |
| 新版範圍：建議 | 6 |
| 新版範圍：不建議 | 9 |

沒有找到範本用到、但官方已改名或棄用的欄位、事件或工具名。hook 的事件名、輸出格式、exec form（`args`）、`Agent` 工具名、`omitClaudeMd`、`permissions.deny` 的 `Edit(...)` 寫法都還是現行寫法（見[第 5 節](#5-已核對沒有變動的寫法)）。要改的地方集中在**官方預設行為變了，範本的說明或判斷跟著失準**，主要是三件事：閒置自動壓縮（idle compaction）、fork mode 預設開啟、compact 後 skill 內容的處理方式。

## 1. 基準：上一版是哪一天、有什麼

### 沒有 tag、release、CHANGELOG

- `git tag -l`、`git ls-remote --tags origin`：沒有任何 tag。
- GitHub releases、tags 列表：都是空的。
- repo 裡沒有 CHANGELOG 檔。

所以用**初版 commit `6404530` 的日期 2026-10-10** 當「上一個 tag 日期」。

### git log：目前版本有什麼

| 日期 | commit | 內容 |
|---|---|---|
| 10-10 | `6404530` | 初版：install.py 安裝與移除、環境檢查、AI 安裝 prompt |
| 10-10 | `c41b081` | 依 harness 與跨平台審查修正：`/dispatch-template` 直接叫用（UserPromptExpansion）、AGENTS.md 匯入、POSIX 路徑檢查、分平台安裝說明 |
| 10-11 | `4da984a` | `--protect` 保護原始資料、還原說明、plan mode 接 `/goal` |
| 10-11 | `90affa5` | 驗收修正：`/goal` 手動模式只問設定沒允許的工具、保護範圍加但書 |
| 10-11 | `182c90e`、`8768388` | README 雙語（README.en.md）、同系列表 |
| 10-12 | `427c28b` | 核對引用與主張、訪談式大綱；依 `/doctor prompt-audit` 修 dispatch-template |
| 10-15 | `9b234a8` | 網站淺色／深色切換、派工到驗收圖解 |

裝進使用者專案的元件：

- hook（Python）：`dispatch_gate.py`（PreToolUse:Agent，沒載入 dispatch-template 就擋派工）、`skill_gate_flag_writer.py`（PostToolUse:Skill 與 UserPromptExpansion，記錄叫用過）、`gate_flags.py`（共用：讀 transcript 判斷 compact）、`context_guard.py`（UserPromptSubmit，15 萬 token 提醒）、`ctrl_char_stop.py`（Stop，掃本回合寫過的檔案有沒有控制字元）。
- skill：`dispatch-template`；subagent：`verifier`；規則：`rules/dispatch-and-verify.md`。
- 選裝 session_log：SessionStart 用 PowerShell 注入 `session_log.md`，加上寫入、歸檔腳本。
- install.py：合併 settings.json、`--protect` 寫 `permissions.deny`、新建 CLAUDE.md（有 AGENTS.md 就 `@AGENTS.md` 匯入）、`.gitignore`、備份與移除。
- 文件要求 Claude Code 2.1.292 以上。

### 官方 changelog 的比對區間

官方 CHANGELOG.md 只有版本號、沒有日期，所以用 npm registry（`@anthropic-ai/claude-code` 的 `time` 欄位）對日期：

| 版本 | npm 發布時間（UTC） |
|---|---|
| 2.1.292 | 2026-10-06（範本要求的最低版本） |
| 2.1.296 | 2026-10-09（初版 commit 前的最後一版） |
| 2.1.299 | 2026-10-14（初版後第一版；npm 上沒有 2.1.297、2.1.298） |
| 2.1.309 | 2026-10-22（今天的最新版） |

比對範圍是 **2.1.299 到 2.1.309**，共 11 版。官方 [What's new](https://code.claude.com/docs/en/whats-new/index.md) 週報最新一期是 Week 37（September 7–11, 2026），**這段區間沒有週報，查不到**。

文件頁面本身沒有修訂日期。所以「文件現在這樣寫」不等於「區間內才改」：能在 changelog 對到版本的，我寫出版本號；對不到的就標「何時改的查不到」。

### 各主題在區間內的 changelog 條目

| 主題 | 區間內和範本有關的條目 |
|---|---|
| hooks | 2.1.299 Windows 沒有 Git Bash 時 shell form 的 PreToolUse 改成失敗就擋；2.1.299 UserPromptSubmit 改在 skill 展開前跑；2.1.300 `updatedInput` 改成要驗證；2.1.302 prompt／agent hook 同一事件最多 12 個並行；2.1.309 PowerShell hook 的 exit 2 修正 |
| settings | 2.1.299 新增 `idleCompaction`、`CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS`；2.1.302 `/config` 加 Idle compaction 列 |
| skills | 2.1.299 檔名或資料夾名含隱藏字元、`<`、`>` 的 skill 不再載入；2.1.301 修正 `/rewind` 後 skill 清單消失；2.1.304 compact 後重送 skill 清單、`/reload-skills` 只送新增或改過的 |
| subagents | 2.1.302 fork mode 在 `-p`、SDK、桌面版、VS Code 也預設開啟；2.1.302 桌面版、VS Code 主對話派的 subagent 一律背景執行；2.1.304 修正 subagent 被續問時忘記最近的工作；2.1.307 同時派的 fork 會被告知哪個是自己 |
| plugins、marketplace | 2.1.302 修正 reftable 格式的 git 讓 marketplace 每次重新 clone；`claude plugin eval` 加 `--disallow-tools`。和範本無直接關係 |
| output styles | 區間內沒有條目 |
| CLAUDE.md 與記憶 | 2.1.309 子目錄 CLAUDE.md 超過大小上限只載入開頭。範本的 CLAUDE.md 在根目錄，不受影響 |
| 權限模式 | 2.1.299 plan mode 加一次性提示（bypass 可用時）；2.1.301 第三方供應商的 `-p` 預設 `default` 模式；2.1.304 新增 `/auto-mode-setup`；2.1.309 修正 `Edit(path)` deny 在含 subshell 的指令擋不到重導向 |
| `/goal` | 只有 VS Code 介面摺疊長訊息的修正，行為沒變 |
| 其他 | 2.1.300 transcript 改成也記錄每次 API 請求的 system prompt、工具與參數；2.1.309 `sed -i` 改成一般 Bash 指令，`/rewind` 不還原 |

## 2. 三類對照

### (a) 範本用到、官方已改名、棄用或改了行為的寫法（6 項）

#### a1. 新增閒置自動壓縮（idle compaction），預設開啟

- **範本位置**：`template/.claude/hooks/gate_flags.py`、`dispatch_gate.py`（compact 後要重叫 dispatch-template）；`context_guard.py`（15 萬 token 提醒先補 log 再 `/clear`）；README「已知限制」與 `docs/how-it-works.md` 的流程表。
- **官方變動**：2.1.299 起，對話超過 20 萬 token、閒置約 54 分鐘，就自動壓縮。PreCompact／PostCompact 的 `auto` matcher 也涵蓋這種壓縮。
- **對範本的影響**：
  - 派工閘門：研究生常一段工作後離開座位，回來第一次派工會因為「叫用後發生過 compact」被擋一次。文件目前只說「compact 後沒重載」會擋，沒說使用者沒下 `/compact` 也會發生。
  - context_guard：門檻 15 萬，idle compaction 門檻 20 萬。如果使用者在 15 萬到 20 萬之間收到提醒但沒處理就離開，或在 20 萬以上閒置，回來時對話已經被摘要，但 session_log 還沒補，進度只剩摘要。
  - `gate_flags.py` 靠 transcript 裡的 `"subtype":"compact_boundary"` 判斷 compact。idle compaction 是否也寫這個標記，**官方文件查不到**（transcript 格式沒有文件），要實測。
- **出處**：
  - <https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md>（2.1.299）：「Added idle compaction in the terminal: a 200K+ token conversation left idle for about 54 minutes is compacted before its one-hour prompt cache expires, so your next message doesn't reprocess it all」
  - <https://code.claude.com/docs/en/settings-reference#idlecompaction>：「Idle compaction compacts a long conversation that you've stepped away from, shortly before its prompt cache expires.」
  - <https://code.claude.com/docs/en/hooks#precompact>（matcher 表 `auto` 列）：「Auto-compact when the conversation reaches the auto-compact window, and idle compaction」

#### a2. compact 後，叫用過的 skill 會自動重新注入，但只留開頭 5,000 tokens

- **範本位置**：`gate_flags.py` 開頭說明「之後若發生 compact（skill 內容可能被摘要掉），要重叫」；`dispatch_gate.py` 的擋下訊息；README 派工圖解「compact 後沒重載」。
- **官方行為**：compact 時會把每個 skill 最近一次的叫用重新接在摘要後面，每個最多 5,000 tokens、合計 25,000，截斷時保留開頭。2.1.304 起 compact 後也會重送 skill 清單（描述）。skill 本文重新注入是何時開始的，**changelog 查不到**。
- **對範本的影響**：「skill 內容可能被摘要掉」不精確。實際情況是內容會回來，但可能被截掉後半。`dispatch-template/SKILL.md` 約 4,760 字，其中中日韓文字 2,860 字，粗估 3,500 到 5,000 tokens，正好在上限附近，**精確 token 數查不到**，要用 `/context` 或 `/skill-doctor` 實測。被截的會是檔案後段：「平行派工前的四項檢查」「多樣本評審」「派工後主對話要做的三件事」。compact 後重叫的規則仍然合理（官方疑難排解也這樣建議），但理由要改寫，最重要的內容要往前移。
- **出處**：
  - <https://code.claude.com/docs/en/skills#skill-content-lifecycle>：「When the conversation is summarized to free context, Claude Code re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each.」
  - <https://code.claude.com/docs/en/context-window#what-survives-compaction>：「Truncation keeps the start of the file, so put the most important instructions near the top of `SKILL.md`.」
  - <https://code.claude.com/docs/en/skills#claude-stops-following-a-skill>：「The conversation was compacted: invoke the skill again to restore its full content.」

#### a3. fork mode 預設開啟：Claude 會自己開 fork，而 fork 不吃派工模板、也不吃 `model` 參數

- **範本位置**：`dispatch_gate.py` 的 `EXEMPT_SUBAGENT_TYPES = {"fork"}`；`dispatch-template/SKILL.md`「派工時一律在 Agent tool 顯式帶 `model` 參數」；`rules/dispatch-and-verify.md` 的委派表；README「已知限制」第 4 點（只有 `fork` 免檢）。
- **官方變動**：終端機互動模式從 2.1.232 起、`-p`／SDK／桌面版／VS Code 從 2.1.302 起，fork mode 預設開啟，Claude 可以自己決定開 fork。fork 的模型與主對話相同，不看 subagent 的 `model` 欄位。fork mode 開著時，互動模式下 Claude 也不能「等」一個 subagent，主對話派的 subagent 都在背景跑。
- **對範本的影響**：範本免檢 fork 的理由（fork 繼承完整 context，不需要模板）仍然成立。但現在 fork 是 Claude 自己會選的預設路徑，等於兩條規則被繞過：沒載模板也能派工；主對話是 opus 時，fork 也用 opus 跑，「顯式指定 model、省額度」這條規則對 fork 無效。文件和規則都沒提這件事。
- **出處**：
  - <https://code.claude.com/docs/en/sub-agents#turn-fork-mode-off>：「Fork mode is on by default from Claude Code v2.1.302, and in an interactive terminal session from v2.1.232.」
  - <https://code.claude.com/docs/en/sub-agents#fork-the-current-conversation>：「Claude can start a fork on its own while fork mode is on, as it is by default.」
  - <https://code.claude.com/docs/en/sub-agents#how-forks-differ-from-other-subagents>（表格 Model 列）：「Same as main session」
  - <https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md>（2.1.302）：「Changed fork subagents (`subagent_type: "fork"`) to be on by default in `claude -p`, the Agent SDK, the desktop app and VS Code, as they already are in the terminal; `CLAUDE_CODE_FORK_SUBAGENT=0` turns them off, and `claude mcp serve` never offers them」

#### a4. transcript 是非同步寫入，而且 2.1.300 起變大

- **範本位置**：`ctrl_char_stop.py`（每次 Stop 把整份 transcript 讀進記憶體，再找本回合的 tool_use，timeout 10 秒）；`context_guard.py`（讀 transcript 最後 3 MB 找 usage）；`gate_flags.py`（整份讀進來找 compact 標記）。
- **官方變動**：hook 文件寫明 transcript 是非同步寫入，可能還沒寫進本回合最後的訊息。2.1.300 起，本機 transcript 還會記錄每次 API 請求的 system prompt、工具與參數，檔案會比以前大。
- **對範本的影響**：長 session 的 transcript 變大以後，`ctrl_char_stop.py` 每回合整份讀取、逐行 `json.loads`，更容易碰到 10 秒 timeout。timeout 就 fail-open，檢查會靜默失效。`context_guard.py` 只讀尾端 3 MB，如果最後一筆 assistant usage 被大量新紀錄擠出 3 MB 以外，會回傳 0、不提醒。新紀錄的格式**官方文件查不到**。基準測試（`prep/fresh-install-2026-10` 分支）用 2.1.309 跑過 Stop hook 是正常的，但只是短 session。
- **出處**：
  - <https://code.claude.com/docs/en/hooks#common-input-fields>：「The transcript file is written asynchronously and may lag the in-memory conversation, so it may not yet include the current turn's most recent messages when a hook fires.」
  - <https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md>（2.1.300）：「Changed local session transcripts to also record each API request's system prompt, tools and parameters, so a transcript you choose to share can reproduce a request exactly」

#### a5. `/rewind` 的還原範圍：`sed -i` 不再還原；編輯工具改過的檔案，之後 Bash 的改動會一起還原

- **範本位置**：README「改壞了怎麼還原」：「Claude 用指令改的檔案（`rm`、`mv`、`cp`、腳本寫檔），只有它用編輯工具改的才追蹤得到」，README.en.md、index.html 對應段落也要一起改。
- **官方變動**：2.1.309 起，`sed -i` 改成一般 Bash 指令，`/rewind` 不還原（以前是模擬成檔案編輯）。官方 checkpointing 文件也寫明：Claude 先用編輯工具改過的檔案，之後 Bash 對它的改動也會被 `/rewind` 還原。
- **對範本的影響**：README 列的例外沒有 `sed -i`。「只有編輯工具改的才追蹤得到」說得太絕對：正確的說法是「只被指令改過的檔案追蹤不到」。
- **出處**：
  - <https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md>（2.1.309）：「Changed `sed -i` to get the standard Bash prompt and run as written, not a simulated file-edit preview; like other Bash edits, it is no longer restored by `/rewind`」
  - <https://code.claude.com/docs/en/checkpointing#bash-command-changes-not-tracked>：「Once Claude has edited a file with its file editing tools in your conversation, `/rewind` undoes changes that Bash commands make to that file afterward.」

#### a6. 官方另有 `Workflow` 工具派 subagent，不經過 `Agent` 工具

- **範本位置**：`template/hooks-core.json` 的 PreToolUse `"matcher": "Agent"`；README 開頭「Claude 要把工作交給 subagent 時，得先載入派工模板……沒載入就會被擋下」。
- **官方行為**：dynamic workflow 用 `Workflow` 工具跑一支腳本，腳本自己派很多 subagent。要使用者明講「use a workflow」、加 `ultracode` 關鍵字或開 ultracode 才會用。Workflow 裡的 agent 會不會觸發 `PreToolUse:Agent`，**官方文件查不到**。changelog 提到攔 workflow agent 的地方是 mod 的 `agent.spawn` hook，可見它和一般 `Agent` 呼叫走不同路徑。這個工具何時加入的，區間內 changelog 查不到。
- **對範本的影響**：README 說「派 subagent 沒載模板就會被擋」，在 workflow 路徑上可能不成立。只有使用者自己要求 workflow 才會發生，所以只需要在已知限制寫一句，再實測一次。
- **出處**：
  - <https://code.claude.com/docs/en/tools-reference>（工具表 `Workflow` 列）：「Runs a dynamic workflow: a script that orchestrates many subagents in the background and returns one consolidated result」
  - <https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md>（2.1.300）：「Added support for rewriting a workflow agent's `prompt` and `model` in the `agent.spawn` mod hook, which could only refuse workflow agents before」

### (b) 官方新功能裡適合放進範本的（9 項）

「新手負擔」指使用者照 README 安裝、使用時要多懂或多做的事；只增加維護者工作的不算。

#### b1. SubagentStart hook 注入「回報合約」

- **用途**：dispatch-template 要求每份派工 prompt 結尾「照抄不刪」回報合約，目前靠 Claude 自律。SubagentStart hook 可以用 `additionalContext` 把合約直接塞進每個 subagent 的開頭，變成機制。用 matcher 排除 `fork`（fork 的 agent_type 值是什麼，**官方文件查不到**，要實測）。
- **放哪個檔**：新增 `template/.claude/hooks/subagent_contract.py`；`template/hooks-core.json` 加 SubagentStart；`dispatch-template/SKILL.md` 的「共用尾段」改成「hook 會自動附上，不必照抄」；`install.py` 的 `CORE_FILES`、`OUR_SCRIPTS`；`hooks/tests/run_tests.py` 補案例。
- **新手負擔**：不加重。install.py 一起裝，使用者看不到差異；`/hooks` 確認時多一類 SubagentStart，README 的「五類」要改。
- **出處**：<https://code.claude.com/docs/en/hooks#subagentstart>：「SubagentStart hooks can't block subagent creation, but they can inject context into the subagent.」

#### b2. `showClearContextOnPlanAccept`：核准計畫時順便清 context

- **用途**：`docs/how-it-works.md`「大的工作」要使用者寫完大綱後「開一個新 session（或下 `/clear`）照著做」。這個設定讓 plan mode 的核准選單多一個「核准並清掉 context」的選項，一步做完。
- **放哪個檔**：`docs/how-it-works.md`「長任務」第 2 步加一句可選設定；不要由 install.py 預設寫入。
- **新手負擔**：小。這是可選的一行設定，選單多一個選項，不設也照舊。
- **出處**：<https://code.claude.com/docs/en/settings-reference#showclearcontextonplanaccept>：「Planning can use a lot of context, so this key adds a first option to that menu, Yes, clear context and …, that approves the plan, clears the conversation context, and starts implementing from the plan alone.」

#### b3. sandbox 會吃 `Edit` deny 規則：開了以後 `--protect` 也擋得到腳本寫檔

- **用途**：README 說 `--protect` 擋不到「腳本自己開檔寫入」，要擋得開 sandbox。官方設定文件寫明 sandbox 會把 `Edit` deny 規則加進 OS 層的 `denyWrite`，所以在 macOS、Linux、WSL2 開 sandbox 後，`--protect` 的路徑連腳本都寫不進去。Linux／WSL2 上路徑不能含萬用字元，結尾的 `/**` 會先去掉，所以 install.py 產生的 `/pdf/**` 會變成具體路徑 `/pdf`，可以用。這要在 WSL2 實測。
- **放哪個檔**：README（與 README.en.md）「保護原始資料」段落補一句做法；install.py 不改。
- **新手負擔**：文件多一句，選用。開 sandbox 本身對新手有負擔（Linux 要另外裝套件、指令會被限制），所以只寫成進階選項。Windows 原生不支援。
- **出處**：
  - <https://code.claude.com/docs/en/settings-reference>（sandbox filesystem 段）：「Claude Code adds your permission rules to the same lists: `Edit` allow and deny rules to `allowWrite` and `denyWrite`, `Read` deny rules to `denyRead`, and `WebFetch(domain:...)` allow and deny rules to the `network` domain lists.」
  - <https://code.claude.com/docs/en/sandboxing>：「The sandbox runs on macOS, Linux, and WSL2.」

#### b4. 在文件介紹 `/context`、`/recap`

- **用途**：`/context` 讓使用者自己看 context 用了多少（context_guard 只提醒 Claude）；`/recap` 是同一 session 內的一行回顧，可以和 session_log 的跨 session 接力分開說明，避免使用者搞混。
- **放哪個檔**：`docs/how-it-works.md` 的流程表或「要不要裝 session_log」段。
- **新手負擔**：不加重，是兩個內建指令的說明。
- **出處**：
  - <https://code.claude.com/docs/en/context-window#check-your-own-session>：「To see your actual context usage at any point, run `/context` for a live breakdown by category with optimization suggestions, including which CLAUDE.md and auto memory files loaded.」
  - <https://code.claude.com/docs/en/interactive-mode#session-recap>：「Run `/recap` to generate a summary on demand.」

#### b5. Stop hook 改用 `additionalContext`，顯示成提醒而不是 hook error

- **用途**：`ctrl_char_stop.py` 目前用 `decision: "block"`，畫面上顯示為 hook error，新手可能以為壞了。官方的 `hookSpecificOutput.additionalContext` 一樣會讓對話繼續，但顯示成 hook feedback。
- **放哪個檔**：`template/.claude/hooks/ctrl_char_stop.py`、`hooks/tests/run_tests.py`。
- **新手負擔**：會減輕一點（訊息不那麼嚇人）；但要重測 `stop_hook_active` 與官方「連續 8 次」上限下的行為。
- **出處**：<https://code.claude.com/docs/en/hooks#stop-decision-control>：「Non-error feedback for Claude. The conversation continues so Claude can act on it, but unlike `decision: "block"` it is shown in the transcript as hook feedback rather than a hook error」

#### b6. 包成 plugin，透過 marketplace 發佈

- **用途**：skill、agent、hook 可以用 `/plugin` 一個指令安裝並自動更新。
- **放哪個檔**：要新增 `.claude-plugin/plugin.json`、`hooks/hooks.json`、marketplace 檔，並改 README 安裝段落。
- **新手負擔**：加重。plugin 帶不了 `rules/`、CLAUDE.md、session_log 檔案，也不能寫 `permissions.deny`（plugin 的 settings 只吃兩個鍵），所以還是要跑 install.py，等於兩套安裝。plugin 的 skill 名稱會變成 `<plugin>:dispatch-template`（範本已處理前綴）。
- **出處**：<https://code.claude.com/docs/en/plugins/components#default-settings>：「Two keys take effect, `agent` and `subagentStatusLine`, and every other key is dropped.」

#### b7. 自訂 output style（寫作助理）

- **用途**：官方說自訂 style 可以把 Claude 改成寫作助理，貼近範本「寫作與研究為主」的定位。
- **放哪個檔**：`.claude/output-styles/` 新增一個檔，install.py 要複製。
- **新手負擔**：加重。要多懂一個概念和 `/output-style`；自訂 style 預設拿掉軟體工程指令，程式專案會變差；而且 output style 不會傳到 subagent（verifier 不受影響，也就不能靠它統一回報口吻）。
- **出處**：
  - <https://code.claude.com/docs/en/output-styles>：「A custom style can also turn Claude into something other than a software engineer, such as a writing assistant or a data analyst.」
  - <https://code.claude.com/docs/en/sub-agents#what-loads-at-startup>：「Output style: a subagent runs its own system prompt, so your output style doesn't shape its responses, except in a fork.」

#### b8. 給 verifier 開 subagent `memory`

- **用途**：讓 verifier 累積「常見錯誤」。
- **放哪個檔**：`template/.claude/agents/verifier.md` frontmatter 加 `memory: project`。
- **新手負擔**：多出 `.claude/agent-memory/` 資料夾要管理。更大的問題是和範本「fresh-context 驗收、不給推理過程」的原則衝突：帶記憶的驗收員不再是獨立的第二雙眼睛。
- **出處**：<https://code.claude.com/docs/en/sub-agents#enable-persistent-memory>：「The `memory` field gives the subagent a persistent directory that survives across conversations.」

#### b9. hook 加 `onFailure: "block"`

- **用途**：讓 hook 壞掉時擋下動作，不再靜默放行。
- **放哪個檔**：`template/hooks-core.json`。
- **新手負擔**：加重。範本刻意全部 fail-open，「不會卡住你」。PreToolUse:Agent 加 block，Python 路徑一錯就完全不能派 subagent，對新手是更差的失敗方式。
- **出處**：<https://code.claude.com/docs/en/hooks#block-the-action-when-a-hook-fails>：「To block the action instead, set `"onFailure": "block"` on a `command` or `http` hook. Requires Claude Code v2.1.295 or later.」

### (c) 範本自己做、現在官方有內建功能可以取代的部分（6 項）

#### c1. 用 transcript 的 `compact_boundary` 判斷 compact → 改用 PostCompact hook（可以取代）

- **範本做法**：`gate_flags.py` 每次派工都把 transcript 整份讀進來，找最後一筆 `"subtype":"compact_boundary"` 的時間，和 flag 檔的 mtime 比較。
- **官方內建**：PostCompact hook 在每次 compact 後觸發，`manual` 和 `auto`（含 idle compaction）都有。範本可以在 PostCompact 刪掉該 session 的 flag 檔，閘門只要看 flag 檔在不在。這樣不用讀 transcript，也不依賴沒有文件的內部格式，順便處理 a1、a4。
- **取代程度**：完整取代 compact 判斷。PostCompact 從 2.1.76 就有，不必提高最低版本。
- **出處**：<https://code.claude.com/docs/en/hooks#postcompact>：「Runs after Claude Code completes a compact operation. Use this event to react to the new compacted state, for example to log the generated summary or update external state.」

#### c2. Stop 時解析 transcript 找寫過的檔案 → 改用 PostToolUse 的 `tool_input`（大部分可以取代）

- **範本做法**：`ctrl_char_stop.py` 在 Stop 時讀整份 transcript，找出本回合 Write／Edit／NotebookEdit 的 `file_path`，再用正規表示式從 Bash／PowerShell 指令撈絕對路徑。README 已知限制：「subagent 寫的檔案記在另一份 transcript，也不在檢查範圍」。
- **官方內建**：PostToolUse hook 直接收到 `tool_input`（Write／Edit 是絕對路徑，Bash 是 `command`）；hook 在 subagent 裡也會觸發（輸入帶 `agent_type`）。做法是 PostToolUse 記下路徑，Stop 時只讀這份清單。不必解析 transcript，避開 a4，也補上「subagent 寫的檔案檢查不到」這個限制（subagent 結束時用 SubagentStop 檢查）。
- **取代程度**：Write／Edit 的路徑完整取代；從 Bash 指令撈路徑的正規表示式還是要自己寫。
- **出處**：
  - <https://code.claude.com/docs/en/hooks#posttooluse-input>：「The input includes both `tool_input`, the arguments sent to the tool, and `tool_response`, the result it returned.」
  - <https://code.claude.com/docs/en/hooks#common-input-fields>（`agent_type` 列）：「Present when the session uses `--agent` or the hook fires inside a subagent.」

#### c3. context_guard 自己算 token → status line 的 `context_window.used_percentage`、`/autocompact`（只能部分取代，不建議拿掉）

- **範本做法**：`context_guard.py` 讀 transcript 的 usage 加總，超過 15 萬提醒 Claude 在段落點請使用者補 log 再 `/clear`。
- **官方內建**：status line 拿得到 context 使用百分比，但只顯示給使用者看，Claude 收不到；`/autocompact` 可以調整自動壓縮的時機，但壓縮不等於「補 log 再清」。UserPromptSubmit 的 hook 輸入裡沒有 context token 欄位（**官方文件查不到這種欄位**；`context_tokens` 只出現在 SessionStart 的 resume／fork 輸入和 PreModelSwitch）。
- **取代程度**：部分。「提醒 Claude 先存進度」這件事官方沒有內建，hook 要留著。
- **出處**：<https://code.claude.com/docs/en/statusline>（欄位表 `context_window.used_percentage` 列）：「Pre-calculated percentage of context window used」

#### c4. install.py 新建 CLAUDE.md 時寫 `@AGENTS.md` → 官方會直接讀 AGENTS.md（不取代）

- **範本做法**：專案有 AGENTS.md 時，新建的 CLAUDE.md 第一行 `@AGENTS.md`。
- **官方內建**：2.1.277 起官方會直接讀 AGENTS.md，但**只在沒有 CLAUDE.md 時**才讀。範本一定會建 CLAUDE.md，所以匯入仍然必要；官方也說保留匯入不會讀兩次。「兩個都讀」的設定只能寫在使用者層級的 settings，專案的 settings 會被忽略，install.py 不能代勞。
- **取代程度**：不取代，現在的做法正確。
- **出處**：<https://code.claude.com/docs/en/memory#remove-an-earlier-agents-md-workaround>：「A `CLAUDE.md` containing `@AGENTS.md`: you can leave it.」

#### c5. session_log 開場注入 → auto memory、`/recap`、`--continue`（不取代）

- **範本做法**：SessionStart 注入 session_log 最新 1 筆全文加 2 筆標題，格式固定、由使用者決定內容。
- **官方內建**：auto memory 由 Claude 自己決定記什麼；`/recap` 只回顧同一個 session，最多 400 字；`--continue`／`/resume` 是接回整段舊對話，context 不是新的。三者都不保證「下一個新 session 知道上次做到哪、下一步是什麼」。範本 `docs/how-it-works.md` 已經引用過 auto memory 的原文，現在還是成立。
- **取代程度**：不取代。可以照 b4 在文件裡講清楚差別。
- **出處**：
  - <https://code.claude.com/docs/en/memory#auto-memory>：「Claude doesn't save something every session.」
  - <https://code.claude.com/docs/en/interactive-mode#session-recap>：「Claude Code caps both automatic recaps and `/recap` output at 400 characters.」

#### c6. install.py 合併設定 → plugin 安裝（不取代）

- **範本做法**：install.py 複製檔案、合併 settings.json、寫 `permissions.deny`、建 CLAUDE.md／session_log／TODO、改 `.gitignore`、備份與移除。
- **官方內建**：plugin 能裝 skill、agent、hook，但帶不了規則檔、CLAUDE.md 和 `permissions.deny`（理由同 b6）。
- **取代程度**：只能取代約一半（hook、skill、agent），剩下的還是要 install.py。不取代。
- **出處**：<https://code.claude.com/docs/en/plugins/overview#decide-whether-you-need-a-plugin>：「Use a plugin when you want several skills, subagents, hooks, or MCP servers packaged as one unit.」

## 3. 逐檔對照總表

| 範本檔案 | 相關項目 | 狀態 |
|---|---|---|
| `README.md`、`README.en.md`、`index.html` | a1、a2、a3、a5、a6、b1、b3 | 要改文件：已知限制（idle compaction、fork、Workflow）、還原段落（`sed -i`）、`/hooks` 類別數（若採 b1）；中英文與介紹頁同步 |
| `docs/how-it-works.md` | a1、a2、a3、b2、b4、c5 | 要改：流程表補 idle compaction 與 fork；可補 `showClearContextOnPlanAccept`、`/context`、`/recap` |
| `docs/vs-superpowers.md` | — | 不是官方文件範圍，不比對 |
| `install.py` | b1、c1、c2 | 只在採用新 hook 時改 `CORE_FILES`、`OUR_SCRIPTS`；`@AGENTS.md` 邏輯維持（c4） |
| `tests/test_install.py` | b1、c1、c2 | 跟著 install.py 改 |
| `template/hooks-core.json` | a6、b1、c1、c2 | 格式都是現行寫法（第 5 節）；採用 c1、c2、b1 才加事件 |
| `template/hooks-session-log.json` | — | exec form 呼叫 PowerShell，SessionStart 不能擋，2.1.299、2.1.309 的 PowerShell／Windows 修正不影響 |
| `template/CLAUDE.md.template` | — | 規則「超過 100 行就抽成獨立檔」比官方建議的 200 行嚴格，不衝突 |
| `template/TODO.md.template`、`session_log.md.template` | — | 無相關變動 |
| `.claude/agents/verifier.md` | a3、b8 | frontmatter 欄位都有效；它不是 fork，`model: sonnet` 有效；背景執行時保留的工具涵蓋它列的工具（macOS／Linux 上因為列了 Bash，Glob／Grep 不會出現，提示裡「用 Glob/Bash 確認」仍然可行） |
| `.claude/hooks/dispatch_gate.py` | a2、a3、a6 | 要改說明與擋下訊息的 compact 理由；fork 免檢規則保留但要在文件講清楚代價 |
| `.claude/hooks/gate_flags.py` | a1、a2、a4、c1 | 建議改用 PostCompact 刪 flag，不再讀 transcript |
| `.claude/hooks/skill_gate_flag_writer.py` | — | PostToolUse:Skill 與 UserPromptExpansion 的輸入欄位（`tool_input.skill`、`command_name`）仍是現行寫法 |
| `.claude/hooks/context_guard.py` | a1、a4、c3 | 讀尾端 3 MB 的假設要用大 transcript 實測；保留 hook |
| `.claude/hooks/ctrl_char_stop.py` | a4、b5、c2 | 建議改成 PostToolUse 記錄路徑，或至少限制讀取量 |
| `.claude/hooks/tests/run_tests.py` | b1、b5、c1、c2 | 跟著 hook 改 |
| `.claude/rules/dispatch-and-verify.md` | a3 | 補 fork 的規則：要指定 model 的派工不要用 fork |
| `.claude/skills/dispatch-template/SKILL.md` | a2、a3、b1 | 最重要的內容往前移，壓在 5,000 tokens 內；補 fork 說明；若採 b1，回報合約改由 hook 附上 |
| `.claude/session-log-kit/*` | c5 | 無相關變動 |

## 4. 新版範圍建議

### 必改（4 項）

1. **compact 相關說明改成官方現行行為（a1、a2）**
   - 改什麼：README、README.en.md、index.html、`docs/how-it-works.md`、`dispatch_gate.py`／`gate_flags.py` 的說明與擋下訊息，寫明離開座位也可能被自動壓縮（idle compaction），回來第一次派工會被擋一次；把「skill 內容可能被摘要掉」改成「只留開頭 5,000 tokens」；dispatch-template 的重要段落往前移，並用 `/context` 實測大小。
   - 理由：idle compaction 是 2.1.299 起的預設，範本現在的說明會讓使用者把「回來第一次派工被擋」當成 bug；skill 截斷保留開頭，段落順序直接決定 compact 後還剩下哪些規則。
2. **補 fork 的規則與說明（a3）**
   - 改什麼：在 `rules/dispatch-and-verify.md` 加一條「要指定 model 的派工（haiku 批次、opus 第二意見、verifier）不要用 fork」；README 已知限制寫明 fork 免檢、會用主對話的模型；`docs/how-it-works.md` 流程表補一行。
   - 理由：fork mode 在各介面都是預設，fork 不經過派工模板、也不吃 `model` 參數。範本的兩個核心承諾「派工要寫清楚」「顯式指定模型、省額度」在這條路徑上不成立，文件卻沒說。
3. **修正「改壞了怎麼還原」（a5）**
   - 改什麼：README 三份（中、英、介紹頁）把 `sed -i` 加進例外，並把「只有編輯工具改的才追蹤得到」改成「只被指令改過的檔案追蹤不到」。
   - 理由：2.1.309 改了 `sed -i` 的行為，現在的文字和官方文件不一致，而這段是新手出事時會照著做的地方。
4. **已知限制補 Workflow 路徑（a6）**
   - 改什麼：README 已知限制加一句「使用者要求 dynamic workflow 時，workflow 派出的 agent 不一定經過派工檢查」，並實測一次確認。
   - 理由：README 開頭寫「沒載入就會被擋下」，這是對外的主張，有已知例外就要寫出來。

### 建議（6 項）

1. **閘門改用 PostCompact 刪 flag（c1）**：不讀 transcript、不依賴沒有文件的 `compact_boundary` 格式，也涵蓋 idle compaction。PostCompact 從 2.1.76 就有，最低版本不用動。成本：改 2 支 hook、加 1 個事件、補測試。
2. **ctrl_char_stop 改成 PostToolUse 記錄路徑（c2、a4）**：避開 transcript 變大造成的 timeout，順便補上「subagent 寫的檔案檢查不到」的限制。成本較高（新 hook、狀態檔、測試），如果 10/24 時間不夠，至少先用長 session 的 transcript 實測讀取時間。
3. **SubagentStart 自動附回報合約（b1）**：把「照抄不刪」從自律變成機制，新手看不到差別。要先實測 fork 的 `agent_type`，確認不會注入到 fork 裡。
4. **`docs/how-it-works.md` 補 `showClearContextOnPlanAccept`（b2）**：和「新的 context 只裝執行要用的東西」的做法一致，只是文件裡加一句可選設定。
5. **README「保護原始資料」補 sandbox 做法（b3）**：給 macOS／Linux／WSL2 的人一條連腳本寫檔都擋得住的路，標成進階選項；`/pdf/**` 在 WSL2 的效果要先實測。
6. **文件補 `/context`、`/recap`（b4）**：讓使用者分得清 context_guard、`/recap`、session_log 各管什麼。

### 不建議（9 項）

1. **包成 plugin（b6、c6）**：plugin 帶不了規則、CLAUDE.md、`permissions.deny`，還是要跑 install.py，新手要學兩套安裝。
2. **自訂寫作 output style（b7）**：多一個概念，程式專案會失去軟體工程指令，而且不影響 subagent。
3. **verifier 開 `memory`（b8）**：和 fresh-context 獨立驗收的原則衝突。
4. **hook 加 `onFailure: "block"`（b9）**：違反範本「fail-open、不卡住你」的設計，Python 路徑一錯就不能派工。
5. **ctrl_char_stop 改用 Stop 的 `additionalContext`（b5）**：好處只在訊息比較不嚇人，要重測「最多擋 1 次」的行為；這版先不動，可以和建議第 2 項一起做。
6. **用 status line、`/autocompact` 取代 context_guard（c3）**：官方沒有「提醒 Claude 先存進度」的內建功能，拿掉 hook 會少掉一層保護。
7. **拿掉 `@AGENTS.md` 匯入（c4）**：範本一定會建 CLAUDE.md，官方只在沒有 CLAUDE.md 時才讀 AGENTS.md，匯入仍然必要。
8. **用 auto memory、`/recap` 取代 session_log（c5）**：都不保證跨 session 接得上進度。
9. **提高最低版本（2.1.292 → 2.1.309）**：上面的必改和建議項目都不需要新版本才有的功能（PostCompact、SubagentStart、`showClearContextOnPlanAccept` 都早於 2.1.292）。提高門檻只會讓還沒更新的人多一步，不必要。

## 5. 已核對沒有變動的寫法

不計入上面三類，列出來證明有查過。

| 範本寫法 | 結果 | 官方網址與原文 |
|---|---|---|
| hook 用 `command` 加 `args`（exec form） | 現行寫法；2.1.299 Windows 沒有 Git Bash 時「失敗就擋」只套用在 shell form，範本不受影響 | <https://code.claude.com/docs/en/hooks#block-the-action-when-a-hook-fails>：「On Windows without Git Bash, a shell-form `PreToolUse` or `PermissionRequest` command hook that fails with `onFailure` unset can instead block the tool call.」 |
| hook 全部 fail-open | `onFailure` 沒設時仍然放行 | <https://code.claude.com/docs/en/hooks#block-the-action-when-a-hook-fails>：「On most events, when a hook fails or times out, Claude Code still carries out the action.」 |
| PreToolUse 回 `hookSpecificOutput.permissionDecision: "deny"` | 現行格式（舊的頂層 `decision` 才是棄用的） | <https://code.claude.com/docs/en/hooks#pretooluse-decision-control>：「PreToolUse previously used top-level `decision` and `reason` fields, but these are deprecated for this event.」 |
| Stop 回頂層 `decision: "block"` | 現行格式 | <https://code.claude.com/docs/en/hooks#pretooluse-decision-control>：「Other events like PostToolUse and Stop continue to use top-level `decision` and `reason` as their current format.」 |
| UserPromptExpansion 接 `/dispatch-template` | 仍是官方說的直接叫用路徑；2.1.299 改成 UserPromptSubmit 在 skill 展開前跑，context_guard 不擋 prompt，不受影響 | <https://code.claude.com/docs/en/hooks#userpromptexpansion>：「`UserPromptExpansion` fires on that direct path.」 |
| matcher `Agent` | 工具名沒變 | <https://code.claude.com/docs/en/sub-agents#restrict-which-subagents-can-be-spawned>：「In version 2.1.63, the Task tool was renamed to Agent.」 |
| verifier 的 `omitClaudeMd`、`effort`、`model` | 都是有效欄位 | <https://code.claude.com/docs/en/sub-agents#frontmatter-reference>（`omitClaudeMd` 列）：「Requires Claude Code v2.1.271 or later」 |
| `--protect` 寫 `Edit(/pdf/**)` | 寫法有效，也擋 `>` 重導向；2.1.309 修好含 subshell 的指令擋不到重導向的問題 | <https://code.claude.com/docs/en/permissions#read-and-edit>：「Read and Edit deny rules apply to Claude's built-in file tools, to file commands Claude Code recognizes in Bash, such as `cat`, `head`, `tail`, `sed`, and `tee`, and to the targets of Bash redirections such as `> file` and `< file`.」 |
| `/goal` 不改權限模式、評估模型只讀對話、回合上限寫法 | 都和官方一致 | <https://code.claude.com/docs/en/goal#set-a-goal>：「A goal doesn't change your permission mode.」 |
| plan mode 核准選項「Yes, and use auto mode」 | 名稱沒變 | <https://code.claude.com/docs/en/permission-modes#review-and-approve-a-plan>：「Yes, and use auto mode: approve and start in auto mode.」 |
| AGENTS.md 只在沒有 CLAUDE.md 時才讀 | 和 install.py 的說明一致 | <https://code.claude.com/docs/en/memory#when-claude-code-reads-agents-md>：「By default, Claude reads `AGENTS.md` only when you have no `CLAUDE.md` in your working directory or above it.」 |
| auto memory 的引文「Claude doesn't save something every session」 | 原文還在 | <https://code.claude.com/docs/en/memory#auto-memory>：「It decides what's worth remembering based on whether the information would be useful in a future conversation.」 |
| SessionStart 注入（session_log） | 沒設 matcher，compact 後也會再跑，和官方「compact 後重新注入」的做法一致 | <https://code.claude.com/docs/en/context-window#what-survives-compaction>（表格最後一列）：「Claude Code runs them and adds their output to the compacted context」 |

## 6. 查不到、要實測的事

- idle compaction 會不會在 transcript 寫 `compact_boundary`（影響現行 `gate_flags.py`；採用建議第 1 項就不需要知道）。
- dispatch-template 的精確 token 數（影響 compact 後被截掉多少）。
- Workflow 派出的 agent 會不會觸發 `PreToolUse:Agent`。
- fork 在 SubagentStart 的 `agent_type` 值（影響 b1 的 matcher）。
- 2.1.300 起 transcript 新增紀錄的格式與大小（影響 `ctrl_char_stop.py`、`context_guard.py`）。
- skill 本文在 compact 後重新注入、Glob／Grep 預設不出現（macOS／Linux）是哪一版開始的：區間內 changelog 沒有，查不到。
