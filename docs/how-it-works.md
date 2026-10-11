# 運作方式：一個 session 從開場到收尾

裝好之後，你的專案會多出這些東西：

```
你的專案/
├── CLAUDE.md                 專案說明（原本沒有才會新建）
├── session_log.md            做了什麼（選裝）
├── TODO.md                   還沒做什麼（選裝，跟 session_log 一起）
└── .claude/
    ├── settings.json         hook 設定（原本的設定會保留）
    ├── rules/dispatch-and-verify.md   每個 session 自動載入的規則
    ├── skills/dispatch-template/      派 subagent 時用的 prompt 模板
    ├── agents/verifier.md             負責驗收的 subagent
    ├── hooks/                         四支 hook 和它們的測試
    └── session-log-kit/               session_log 的腳本（選裝）
```

## 一個 session 照什麼順序發生

「機制」是 hook 自動做或自動擋，忘了也會發生；「自律」是寫在規則裡，靠 Claude 照做，不一定每次都做到。

| 階段 | 發生什麼 | 機制或自律 | 在哪裡 |
|---|---|---|---|
| 開場 | 注入 session_log 最新 1 筆全文，加前 2 筆的標題與下一步 | 機制 | `.claude/session-log-kit/sessionstart_log.ps1` |
| 開場 | Claude 用 1 到 2 句報告上次進度與待辦 | 自律 | CLAUDE.md 的接力說明 |
| 工作中 | 預設自己做，有三種好處之一才派 subagent | 自律 | `.claude/rules/dispatch-and-verify.md` 第一原則 |
| 派 subagent 前 | 先載入 `dispatch-template`：寫清楚目標、驗收條件、回報格式，指定模型 | 機制，沒載就擋 | `.claude/hooks/dispatch_gate.py` |
| 派工沒過 | 第一次先追問同一個 subagent，再不過才換更強的模型，附上失敗經過 | 自律 | 規則檔「升降級路徑」 |
| 宣告完成前 | 依風險分三級驗收：0 級不驗、1 級跑腳本貼輸出、2 級派 `verifier` | 自律 | 規則檔「驗證不自驗」 |
| 工作中 | 主對話超過 15 萬 token 時，提醒先補 log 再下 `/clear` | 機制，只提醒 | `.claude/hooks/context_guard.py` |
| 回合結束 | 這一回合寫過的 .md／.json／.py 裡有控制字元就擋下 | 機制 | `.claude/hooks/ctrl_char_stop.py` |
| 收尾 | session_log 最上面補一筆，用腳本插入、檢查格式 | 自律＋腳本檢查 | `.claude/session-log-kit/add_session_log.py` |
| 收尾 | TODO 做完的刪掉，新的待辦照格式寫 | 自律 | `TODO.md` 開頭的說明 |

hook 全部 fail-open：hook 自己出錯時一律放行，不會卡住你，但壞掉時也不會有提示。

## 要不要裝 session_log

問一句：這個專案的進度，事後查得到嗎？

- 查不到（Obsidian 筆記庫、論文資料夾、沒用 Git 的文件專案）：裝。不然每次開 session 都要重講一次上次做到哪。
- 查得到（程式 repo，看 git log 和 PR 就知道）：可以不裝，待辦另外記在 `TODO.md` 就好。

`install.py` 沒指定時會自己判斷：專案不在 git repo 裡就裝，在 git repo 裡就不裝。

session_log 跟 Claude Code 內建的 [auto memory](https://code.claude.com/docs/en/memory#auto-memory) 可以並用。auto memory 預設開啟，由 Claude 自己判斷什麼值得記，官方原文是「Claude doesn't save something every session」，所以不保證記下上次做到哪。session_log 的內容由你決定、格式固定，每次開場一定注入。

## 長任務：先規劃，再用 `/goal` 跑到完成

改一整章、整理一批文獻筆記這類動到很多檔案、要跑很多回合的工作，照這三步：

1. **先規劃**：按 `Shift+Tab` 切到 plan mode（或在訊息前加 `/plan`），請 Claude 讀檔、提計畫。plan mode 裡 Claude 只讀不改。計畫要附一份可以逐條勾選的驗收條件，例如「第二章每段都有引用」「`notes/` 每份筆記的研究問題、方法、發現三欄都填了」。寫成一段散文的計畫，請它重寫。
2. **核准時選 auto mode**：計畫好了，Claude Code 會問你要不要執行，選「Yes, and use auto mode」（auto mode 不能用時，例如組織關掉了，這個選項會變成「Yes, auto-accept edits」）。下一步的 `/goal` 不會改權限模式，留在手動模式的話，設定沒允許的工具呼叫都會停下來問你。
3. **設 `/goal`**：打 `/goal` 加上完成條件，Claude 會一回合接一回合做，直到另一個模型判斷條件達成。這個判斷的模型只讀對話內容，不會自己跑指令或開檔，所以條件要寫成「對話裡看得到的證據」。

條件寫法（官方 [goal 文件](https://code.claude.com/docs/en/goal)建議要有終點、證明方式、途中不能動的東西，再加回合上限）：

```text
/goal 計畫的驗收條件逐條在對話裡貼出檢查結果，verifier 的報告已貼出且沒有致命或錯誤等級的問題；不得修改 pdf/ 與 data/；或跑滿 20 回合就停
```

小改動不用這樣做，直接交代就好。plan mode 裡第一次派 `Explore` 或 `Plan` 可能會被派工檢查擋一次，載入 `dispatch-template` 後就會放行（見 README 已知限制）。

## 改成自己的版本

- 規則寫在 `.claude/rules/dispatch-and-verify.md`，派工模板在 `.claude/skills/dispatch-template/SKILL.md`，直接改就好。同一條規則只寫在一個地方，不然改了一邊，另一邊會過時。
- 改之前先備份或 commit 一次，改壞了才還原得回來。
- 改了 hook 就跑 `python .claude/hooks/tests/run_tests.py`。要加自己的 hook，照現有檔案的寫法：從 stdin 讀 JSON、出錯就放行、狀態檔放在 hook 旁邊，並在測試裡補案例。
