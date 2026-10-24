---
name: setup
description: 用 plugin 裝好 workflow-kit 之後，在專案裡建 CLAUDE.md、session_log.md、TODO.md、派工規則檔，問要鎖哪些資料夾、要不要開 /todo 側欄。使用者打 /workflow-kit:setup 時才跑。
disable-model-invocation: true
---

# workflow-kit 專案設定

plugin 帶得了 hook、skill、agent，帶不了規則檔、CLAUDE.md、`permissions.deny` 和 statusLine。這份 skill 把這幾樣寫進目前的專案。照下面的順序做，一次只問使用者一題，每個要寫的檔先說要寫什麼、等使用者同意再寫。

本 skill 用到的路徑：

- plugin 裡的範本：`${CLAUDE_PLUGIN_ROOT}/template/`
- hook 用的 Python 指令：`${user_config.python}`
- 專案資料夾：目前的工作資料夾（下面寫「專案」都指它）

寫 `.claude/` 底下的檔時，Claude Code 一定會跳出權限詢問，自動接受編輯的模式也一樣。先跟使用者說這是正常的，請使用者按允許。被拒絕的話不要改用指令繞過，在收尾時列出沒寫成的檔和它該有的內容。

## 1. 先檢查能不能裝

逐項檢查，任一項不過就停下來，告訴使用者原因和怎麼處理，不往下做。

1. 專案裡有 `.claude/hooks/dispatch_gate.py`：代表已經用 install.py 裝過。兩種裝法同時在，同一個 hook 會跑兩次。請使用者二選一：留 install.py 版就跑 `claude plugin uninstall workflow-kit --scope project`；改用 plugin 版就在 template 資料夾跑 `python install.py <專案> --uninstall`。
2. 跑 `${user_config.python} --version`，要 3.8 以上。這一行如果原樣出現 `${user_config.python}`、或指令跑不起來、或版本太舊，代表「Python 指令」還沒設或設錯，hook 全都不會跑。請使用者打 `/plugin configure workflow-kit@workflow-kit`，選這台電腦跑得動的那個（Windows 通常是 `python`，macOS、Linux 多半是 `python3`），沒有 Python 就先裝，然後重開 Claude Code 再打 `/workflow-kit:setup`。
3. 專案就是使用者的家目錄或磁碟根目錄時，先確認使用者真的要裝在這裡。

## 2. CLAUDE.md

- 專案沒有 `CLAUDE.md`（也沒有 `.claude/CLAUDE.md`）：讀 `${CLAUDE_PLUGIN_ROOT}/template/CLAUDE.md.template`，裡面每個【】一次問一題，用使用者的回答填。使用者說「先跳過」的就留著【】。範本裡寫「已用 `permissions.deny` 鎖住」的句子，等第 4 步真的寫進 `.claude/settings.json` 之後才保留；使用者不鎖或沒寫成，就把那幾句刪掉，不要留下不實的說明。專案已有 `AGENTS.md` 時，CLAUDE.md 第一行寫 `@AGENTS.md`，因為有了 CLAUDE.md，Claude Code 就不再自動讀 AGENTS.md。
- 已經有 CLAUDE.md：不覆蓋。把範本有、現有檔沒有的段落列給使用者，問要不要補，補的話加在結尾。

不論新建或既有，結尾都加這段接力說明（已經有 `claude-workflow-template:start` 標記就不重複加）：

```
<!-- claude-workflow-template:start -->
## 接力：session_log 與 TODO

- 開場時 hook 會注入 `session_log.md` 最新 1 筆全文，以及前 2 筆的標題與下一步。先用 1 到 2 句話報告上次進度與待辦，再處理指令。
- 每完成一段有意義的工作，把新紀錄存成暫存檔，用開場注入第一段給的指令插到最上面。格式見 workflow-kit 的 session-log-kit README。
- 還沒做的事寫在 `TODO.md`，做完就整條刪掉。
<!-- claude-workflow-template:end -->
```

## 3. session_log.md、TODO.md、派工規則檔

把下面三個檔從範本複製到專案，已經存在的不動，改成告訴使用者「已經有了，沒動」，有明顯差異時列出差異請使用者決定。

| 專案裡的檔 | 範本 |
|---|---|
| `session_log.md` | `${CLAUDE_PLUGIN_ROOT}/template/session_log.md.template` |
| `TODO.md` | `${CLAUDE_PLUGIN_ROOT}/template/TODO.md.template` |
| `.claude/rules/dispatch-and-verify.md` | `${CLAUDE_PLUGIN_ROOT}/template/.claude/rules/dispatch-and-verify.md` |

規則檔放在 `.claude/rules/`，Claude Code 每個 session 都會自動載入。plugin 升版時這份不會跟著更新，README 的「更新」一節有說明怎麼比對新版。

專案在 git repo 裡時，問使用者 `session_log.md` 要不要進版控。不要的話在 `.gitignore` 加一行 `session_log.md`。

## 4. 鎖住不能改的資料夾

問使用者：「專案裡有沒有 Claude 不能改的檔案或資料夾？例如原始 PDF、問卷原始資料、別人給的檔案。」

- 沒有就跳過這步。
- 有的話，每個路徑先確認存在，再換成規則。專案裡的資料夾寫 `Edit(/相對路徑/**)`，單一檔案寫 `Edit(/相對路徑)`，專案外的路徑寫 `Edit(//絕對路徑/**)`（Windows 的 `D:\data` 寫成 `//d/data/**`）。路徑含 `* ? [ ]` 的不要自己轉，請使用者手動寫。整個專案資料夾不能鎖，鎖了 Claude 什麼都改不了。
- 把要寫進 `.claude/settings.json` 的 `permissions.deny` 整段列出來，原本就有的規則留在前面，等使用者說可以才寫。settings.json 原本的其他設定全部保留。
- 寫完告訴使用者：這些規則擋得到 Claude 的編輯工具和 `>` 這類輸出重導向，擋不到 Python 等腳本自己開檔寫入。

## 5. /todo 側欄（選用）

問使用者要不要開 /todo 側欄。要的話先確認 todo plugin 已經裝了（`claude plugin list` 看得到 `todo@workflow-kit`），沒裝就給安裝指令 `claude plugin install todo@workflow-kit --scope project`，請使用者自己跑。

接著問要列哪些專案（名稱與 TODO 檔的路徑），照 todo plugin README 的格式寫 `todo.config.json`，寫之前一樣先列出內容等使用者同意。

## 6. 狀態列（只告訴使用者怎麼做）

plugin 不能改底部狀態列，狀態列又是使用者的全域設定，所以這步不替使用者寫。只告訴使用者：想在底部看到模型和 context 用了多少，可以自己打 `/statusline 顯示模型名稱和 context 用量百分比`，Claude Code 會在 `~/.claude/` 產生腳本並改設定，過程中會問要不要允許。不要就跳過。

## 7. 收尾

1. 列出這次建立或修改的檔案，每個一行，寫明是新建、有改、還是已經有了沒動。
2. 印出 `.claude/settings.json` 目前的內容。
3. 請使用者關掉 Claude Code、在同一個資料夾重開，打 `/hooks` 確認看得到 workflow-kit 的 6 個 hook（派工前檢查、skill 叫用紀錄 2 個、context 提醒、控制字元檢查、session_log 開場）。
4. 下次開場會自動帶入 session_log，第一次因為還沒有紀錄，只會看到範本的說明。
