[繁體中文](README.md) | English

# claude-workflow-template

A Claude Code workflow setup for graduate students. Install it into your own project folder (thesis, literature notes, reports) and it works from there. Once installed:

- Each session picks up where the last one stopped. Claude reads the previous log at startup and tells you in a sentence or two where things stand and what's left.
- Delegation has to be spelled out first. Before Claude hands work to a subagent, it must load the dispatch template and state the goal, the acceptance criteria, and the report format. If it skips the template, the call is blocked.
- Finished work is checked by a different agent. Important output (thesis paragraphs, anything you publish) goes to a `verifier` that took no part in making it.
- A few common mistakes are caught automatically. Invisible control characters written into files get blocked, and you get a reminder to save your progress when the conversation runs long.
- Raw data can be locked. Folders or files you name at install time (PDFs, raw survey files) can't be changed by Claude through its edit tools or `>` redirection. A script that Claude writes, such as a Python script that opens the file itself, is not blocked.

Some terms: a **hook** is a small program Claude Code runs automatically at set points (session start, before a tool call, end of a turn); it can feed Claude extra information or block an action. A **subagent** is a separate assistant Claude starts, which does one job in its own conversation and reports back. **Context** is what Claude currently remembers of this conversation; when it gets too long, `/clear` wipes it and you start fresh.

**Language note**: everything this template installs is written in Traditional Chinese: the rules, the dispatch skill, the `verifier`, the CLAUDE.md template, hook messages, and `install.py` output. If Claude's replies drift into Chinese, add a line to your CLAUDE.md asking it to reply in English. You will see Chinese text in block messages and in the files under `.claude/`. The intro page and the docs in `docs/` are also in Chinese.

Intro page (Chinese): <https://wayhong0928.github.io/claude-workflow-template/>

## Who it's for

- You use Claude Code (the terminal version), and your project spans many sessions.
- Your project is mostly writing and research: theses, literature notes, reports. Code projects work too, but for pure programming a package like [Superpowers](https://github.com/obra/superpowers) is a better fit (comparison, in Chinese: [docs/vs-superpowers.md](docs/vs-superpowers.md)).
- Platforms: run on real hardware on native Windows; the hook and installer tests pass on WSL2 (Ubuntu); macOS hasn't been tested. The hooks and session_log scripts are all Python; PowerShell is not needed.
- Account: Claude Code requires a login. The account types the official docs list are the paid Pro, Max, Team, and Enterprise plans, or a Claude Console account (prepaid API credits); the free plan is not among them (official [quickstart](https://code.claude.com/docs/en/quickstart)). Without a paid plan, the [one-hour quickstart](https://wayhong0928.github.io/mis-thesis-guide/pages/ai-quickstart.html) in the same series uses only the web apps.

You don't need to know Git. To undo damage, see [Undoing a bad change](#undoing-a-bad-change).

## Before installing: check your environment

| Tool | What it's for | Required? | How to check | If you don't have it |
|---|---|---|---|---|
| Claude Code 2.1.292 or later | This setup is built for it | Yes | `claude --version` | Install per the [official guide](https://code.claude.com/docs/en/setup). To update: native install `claude update`; WinGet `winget upgrade Anthropic.ClaudeCode`; Homebrew `brew upgrade claude-code` |
| Python 3.8 or later | All hooks, the session_log scripts, and the installer | Yes | Windows: `python --version` (or `py --version`); macOS, Linux, WSL: `python3 --version` | Windows: `winget install Python.Python.3.12`; macOS: `brew install python` (needs [Homebrew](https://brew.sh) first; if you'd rather not install it, use the installer from [python.org](https://www.python.org/downloads/)); Ubuntu/WSL: `sudo apt install python3` |
| Git | Downloading this template for the fallback install | No | `git --version` | Download the ZIP instead |

On Windows, if typing `python` opens the Microsoft Store, Python isn't installed yet; that's just a built-in shortcut.

Where the version floor comes from: the features this setup uses (the `args` form for hooks and the `${user_config.*}` plugin settings) all exist by 2.1.207 at the latest. Real-hardware testing used 2.1.309 and 2.1.310; versions 2.1.292 through 2.1.308 were not tested one by one.

**If the same folder is opened from two systems**: the Python command name the hooks use (`python` or `python3`) is set for the environment you install in. If the project sits on a cloud drive opened from both Windows and a Mac, or the same folder is opened from both Windows and WSL, every hook fails on the other side and the dispatch check stops working with them. In that case, use Claude Code on only one side.

**If you use WSL**: run Claude Code and Python inside WSL, and keep the project on the WSL side.

## Install: let an AI install it as a plugin (recommended)

Open Claude Code in **your project folder** (open a terminal there and type `claude`) and paste in the whole block below. Before each step it tells you what it will run and waits for your OK.

```text
Please install workflow-kit (https://github.com/wayhong0928/claude-workflow-template) in the current folder. Before each step, tell me which command you will run and wait for my OK.
1. Check that claude --version is 2.1.292 or later; for Python, try python, python3, py in that order (py only on Windows), needs 3.8 or later; on Windows, if the Microsoft Store opens or it prints "Python was not found", count it as missing. If anything is missing, stop and tell me how to install it.
2. Run claude plugin marketplace add wayhong0928/claude-workflow-template
3. Run claude plugin install workflow-kit@workflow-kit --scope project --config python=<the Python command found in step 1>
4. Ask me to quit Claude Code, reopen it in the same folder, and type /workflow-kit:setup, then answer its questions one at a time. The setup skill is written in Traditional Chinese; ask me its questions in English and write my answers in English.
```

`--scope project` enables it only in this folder; other projects aren't affected. Always pass `--config python=`: without it, none of the hooks run. Setup creates `CLAUDE.md`, `session_log.md`, `TODO.md`, and the dispatch rules file, and asks which folders to lock. When it writes files under `.claude/`, Claude Code asks for your permission first; that's expected.

**Check this yourself afterwards**: restart `claude` and type `/hooks`. You should see workflow-kit's 7 hooks (`PreToolUse`, `PostToolUse`, `PostCompact`, `UserPromptExpansion`, `UserPromptSubmit`, `Stop`, `SessionStart`).

### When a work computer blocks outside plugin sources

On computers managed by a company or school, an administrator can use `strictKnownMarketplaces` to allow plugins only from approved sources (official docs: [plugins/org](https://code.claude.com/docs/en/plugins/org#restrict-what-users-can-install)), and step 2 will fail. Use the fallback install below instead: it only copies files into your project and doesn't go through the plugin system. If your employer forbids downloading outside code, ask IT before installing.

### Updating

- Plugin: run `claude plugin marketplace update workflow-kit`, then `claude plugin update workflow-kit@workflow-kit`, and restart Claude Code. The hooks, skills, and verifier switch to the new version. The `.claude/rules/dispatch-and-verify.md` that setup copied into your project doesn't change; to update it, ask Claude to compare it with the new version and decide.
- Fallback install: download the new version and run install.py again as below; it backs up before overwriting.

## Fallback: install with install.py

Use this when a work computer can't install plugins, or when you want every file inside your project to manage yourself. Open Claude Code or Codex in **your project folder** (type `claude` or `codex`) and paste in the whole block below. It checks your environment first, asks before installing anything missing, and waits for your OK at every step. Don't run this in a project that already has the plugin; install.py detects it and stops.

Codex can do the install, but what gets installed only works in Claude Code: Codex reads `AGENTS.md`, `.agents/skills/`, and `.codex/hooks.json`, not `.claude/`. Codex's default sandbox has no network access and can only write to the current folder, so it will ask you to approve the download of the template into a temp folder.

```text
Please install claude-workflow-template (https://github.com/wayhong0928/claude-workflow-template) into the current folder. Before each step, tell me what you are about to do and which command you will run, and wait for my OK. Don't edit any existing files in my project yourself; leave every change to its install.py (it makes backups first).

1. Check the environment and report each item as present/missing with its version:
   - Operating system, and whether this is WSL (on Linux, /proc/version containing "microsoft" means WSL). If it is WSL, the claude and python3 below must be the ones installed inside WSL, not on the Windows side.
   - Claude Code: claude --version, needs 2.1.292 or later.
   - Python: try python, python3, py in that order (py only on Windows), needs 3.8 or later. On Windows, if the Microsoft Store opens or it prints "Python was not found", count it as missing.
   - Git: git --version.
2. If Python is missing or Claude Code is too old: stop, tell me how to install or update it (Python: winget install Python.Python.3.12 on Windows, brew install python on macOS, sudo apt install python3 on Ubuntu/WSL; Claude Code depends on how it was installed: claude update for a native install, winget upgrade Anthropic.ClaudeCode for WinGet, brew upgrade claude-code for Homebrew), and ask whether to do it now. If I say no, stop here.
3. If Git is missing: ask whether to install it (Windows: winget install Git.Git; macOS: xcode-select --install; Ubuntu/WSL: sudo apt install git). If I say no, that's fine; download the ZIP in the next step instead.
4. Download version v1.0.0 of the template into a temp folder, not into my project. With Git, use git clone --branch v1.0.0 --depth 1 https://github.com/wayhong0928/claude-workflow-template.git; without it, download https://github.com/wayhong0928/claude-workflow-template/archive/refs/tags/v1.0.0.zip and unzip it.
5. Ask whether I want session_log (each session automatically picks up the previous one; it adds session_log.md and TODO.md to the project). Give me a one-line recommendation: if this folder is not a git repo (for example a thesis folder or an Obsidian vault), recommend it; if it's a code repo, it can be skipped. Then ask whether there is raw data you must not change (PDFs, raw survey files, submitted documents), and if so, list the folders or files.
6. Dry run first: python <temp folder>/install.py <my project folder> --dry-run, plus --session-log or --no-session-log; for each raw-data path from step 5, add --protect <path>. Walk me through the actions it lists; once I agree, run it again without --dry-run. Replace python with the one you found in step 1.
7. In my project folder, run python .claude/hooks/tests/run_tests.py (again with the python from step 1). The last line reads "N/N 通過" ("通過" means passed); if the two numbers match, everything passed. If it doesn't pass, paste the output to me and don't modify the hooks yourself.
8. If install.py says it created a new CLAUDE.md: the file is in Traditional Chinese. Ask me one question at a time to fill in the 【】 placeholders, explaining each line in English and writing my answers in English; delete any line I can't answer.
9. Delete the temp folder. Report the version installed (if you downloaded with Git, include the output of git rev-parse --short HEAD run in the temp folder before deleting it), what was installed, what already existed, where the backup is, and which steps failed or were skipped by me. Finally, remind me to quit Claude Code, type claude again in the project folder, and type /hooks to confirm.
```

**After the AI finishes, check this yourself**: in the project folder, start `claude` again and type `/hooks`. You should see six event types: `PreToolUse`, `PostToolUse`, `PostCompact`, `UserPromptExpansion`, `UserPromptSubmit`, `Stop` (plus `SessionStart` if you installed session_log).

### Without an AI: run install.py yourself

The commands below assume the project folder is `thesis-notes` in your home folder (`~` means your home folder and works on Windows, macOS, and Linux); replace it with your own. If the path has spaces, wrap the whole path in quotes. On macOS, Linux, and WSL, replace `python` with `python3`.

1. Download the [v1.0.0 ZIP](https://github.com/wayhong0928/claude-workflow-template/archive/refs/tags/v1.0.0.zip) and unzip it anywhere (not inside your project). If you use Git, `git clone --branch v1.0.0 --depth 1` works too.
2. Open a terminal in the unzipped folder (Windows: right-click an empty spot in the folder and choose "Open in Terminal"; macOS: open Terminal, type `cd ` with a trailing space, drag the folder into the window, and press Enter; Linux, WSL: `cd` into it), then do a dry run (replace the path with your project):

   ```
   python install.py ~/thesis-notes --session-log --dry-run
   ```

   It lists how many files it will add, which files it will overwrite, and which settings it will change, without touching anything. To skip session_log, replace `--session-log` with `--no-session-log`; if you give neither, it decides for you (it installs session_log when the project isn't in a git repo). If you have raw data that must not change, add options like `--protect pdf` (see [Protecting raw data](#protecting-raw-data)).
3. If it all looks right, run it again without `--dry-run`.
4. In the terminal, `cd ~/thesis-notes` to switch to your project folder and run `python .claude/hooks/tests/run_tests.py`. The last line reads "N/N 通過" ("通過" means passed); if the two numbers match, everything passed.
5. Open `CLAUDE.md` in your project and fill in the 【】 placeholders (if install.py created it).
6. In the project folder, type `claude`, then `/hooks` to confirm.

### What install.py does

- Copies the files under `template/.claude/` into your project's `.claude/`.
- Merges the hook settings into `.claude/settings.json`. Your existing settings stay; it only adds these entries. If you passed `--protect`, it also adds protection rules to `permissions.deny` in the same file.
- Installs the to-do feature only when you pass `--todo` (off by default, so nothing extra prints at session start): copies the two scripts from `todo/scripts/` into `.claude/todo/` and adds two hooks to settings.json, one that lists your to-dos at session start and one that checks the first-line format when a TODO file is edited. The list reads `todo.config.json` in the Claude Code config folder (format in [todo/README.md](todo/README.md)); until that file exists, session start prints a single line saying the config file is missing. That line mentions `/workflow-kit:setup`, which is a plugin command, so on this route write the config by hand following todo/README.md.
- Creates a `CLAUDE.md` only if the project doesn't have one. If the project already has an `AGENTS.md`, the first line of the new CLAUDE.md is `@AGENTS.md`, which imports it; without that line, Claude Code stops reading AGENTS.md automatically once a CLAUDE.md exists. When session_log is installed, it appends a handoff section to the end of CLAUDE.md, wrapped in `<!-- claude-workflow-template:start -->` and `<!-- claude-workflow-template:end -->` markers.
- When session_log is installed, creates `session_log.md` and `TODO.md` only if they don't exist.
- If the project is in a git repo, adds the local state files the hooks create and the install backup folder `.claude/backup/` to `.gitignore`.

Before overwriting or modifying anything (including `.gitignore`), it backs up the old files to `.claude/backup/workflow-template-<timestamp>/`. Running it again doesn't add settings twice, so to update later, download the new version and run it again.

### Uninstalling

```
python install.py ~/thesis-notes --uninstall
```

Add `--dry-run` to see what it will do first. Uninstalling does the following, and backs up to `.claude/backup/` before deleting or changing anything:

- Removes this template's hooks from settings.json. If what's left matches the backup taken before install, it puts that backup back as it was (formatting unchanged); if the file was created by the install and is empty once the hooks are gone, it deletes it. Protection rules in `permissions.deny` are left in place so your raw data stays protected; delete them from settings.json yourself if you no longer need them.
- Deletes the files it installed in `.claude/` and the hooks' state files. If you installed with `--todo`, `.claude/todo/` and its two hooks go too (`todo.config.json` lives in the config folder and is left alone). If an earlier backup holds an old file at the same path (possibly a file of the same name you had before installing), it lists the location at the end; copy it back yourself if you want it.
- Removes the marked section from CLAUDE.md. If `CLAUDE.md`, `session_log.md`, or `TODO.md` is still the template created at install and you haven't changed it, it deletes it; anything you changed is your content and is kept.
- Removes the hook state lines from `.gitignore`. The `.claude/backup/` line stays so `git add .` doesn't pick up the backups; once you're sure you don't need the backup folder, delete it and that line together.

## Using it day to day

Wang Xiaoming keeps the literature notes for a master's thesis in an Obsidian folder, without Git.

1. Install as above, with session_log. Fill in CLAUDE.md like this:
   - What this project is: "You are Wang Xiaoming's literature-notes assistant. Project goal: every paper read has a note covering its research question, method, and main findings."
   - Rules that must not be broken: "All citations in APA 7th edition." `pdf/` must not change, so `--protect pdf` was added at install time and Claude Code blocks Claude's edits to it, whether or not Claude remembers the rule.
2. Always start `claude` in the notes folder, or the hooks and CLAUDE.md won't load.
3. At startup Claude says where the last session left off. Give it work as usual.
4. When a piece of work is done, tell Claude "update the log". It adds an entry at the top of `session_log.md` in the set format and updates `TODO.md`. You'll see that entry at the start of the next session.
5. When Claude delegates to a subagent, you'll see it load `dispatch-template` first. For important output, it sends the work to `verifier` before saying it's done.

The session_log entry format is described (in Chinese) in [template/.claude/session-log-kit/README.md](template/.claude/session-log-kit/README.md); when each mechanism fires is covered in [docs/how-it-works.md](docs/how-it-works.md).

### From delegation to acceptance

```mermaid
flowchart TD
  A{"Delegate to a subagent?"} -- "No" --> Z["Main session does it"]
  A -- "Yes" --> B["Load dispatch-template (once per session)<br/>state goal and motivation, acceptance criteria, report format, model"]
  B -. "not loaded, or not reloaded after the conversation was compacted (auto-compaction included)" .-> G["dispatch_gate.py blocks"]
  B --> C["Subagent reports back"]
  C --> D{"Check by the three levels"}
  D -- "Pass" --> E["Done"]
  D -- "Details wrong" --> F["Follow up with the same agent once"]
  D -- "Wrong direction" --> U["Re-delegate to a stronger model<br/>with the failure record"]
  F -- "Still fails" --> U
  U -- "Opus fails too" --> X["Stop and let the user decide"]
```

## Protecting raw data

Lock things that must not change, such as PDFs, raw survey files, and submitted documents, with `--protect` at install time. It takes folders or files, as many times as you like:

```
python install.py ~/thesis-notes --session-log --protect pdf --protect data/survey_raw.csv
```

It adds this to `.claude/settings.json`:

```json
"permissions": {
  "deny": ["Edit(/pdf/**)", "Edit(/data/survey_raw.csv)"]
}
```

`/pdf/**` means every file under `pdf/` in the project; a path outside the project is written as an absolute path like `//d/research-data/**`. When Claude changes a file with its edit tools or writes output into it with `>`, Claude Code blocks it, even in the mode that skips permission prompts (tested on Windows with Write, Edit, and `>`). To add more later, run install.py again with `--protect`; existing rules aren't duplicated. You can also edit settings.json directly in the format above.

What it can't block: Claude writing a script, such as a Python script, that opens the file and writes to it itself. The official [permissions docs](https://code.claude.com/docs/en/permissions#read-and-edit) say this kind of indirect write is out of scope. Blocking that too requires the OS-level [sandbox](https://code.claude.com/docs/en/sandboxing), which supports only macOS, Linux, and WSL2. So keep a backup of important raw files outside the project.

A line in CLAUDE.md saying "don't modify `pdf/`" is only a reminder; Claude won't always follow it. To actually block changes, use `--protect`.

## Undoing a bad change

Claude Code saves a checkpoint each time you send a message. If a file gets damaged, type `/rewind` (or press `Esc` twice while the input box is empty), pick the message to go back to, then choose whether to restore code, the conversation, or both. See the official [checkpointing docs](https://code.claude.com/docs/en/checkpointing).

What `/rewind` can't recover:

- Files changed only by commands (`rm`, `mv`, `cp`, `sed -i`, scripts writing files). If Claude edited a file with its edit tools first, later command changes to that file are restored along with it.
- Files changed by a subagent, in most cases.
- Files you changed yourself outside Claude Code.
- Checkpoint file snapshots are cleaned up after about 30 days by default.

So keep a long-term version history separately: if you use Git, run `git init` in the project folder and ask Claude to commit after each piece of work; if you don't, at least copy the folder before a big change.

## Checking citations and claims

When a thesis section or a set of literature notes is done, ask Claude to send it to `verifier` to check the citations. `verifier` took no part in the writing and gets only the acceptance criteria and file paths. The more specific the criteria, the more accurate the check:

```text
Send chapters/ch2.md to verifier to check its citations:
1. Every (Author, Year) in the text appears in references.md, and every entry in references.md is cited in the text.
2. The claim next to each citation matches what the original paper in pdf/ says; for any mismatch, quote the sentence from the original.
3. For each entry in references.md with a DOI, the authors, year, and title on the DOI page match what references.md says.
```

It checks entry by entry by reading files and the web, with no automated script, so:

- It can't read full text behind a paywall and will mark those "can't determine". Put the PDF in the project and give its path in the criteria so it can check against the original.
- It can miss things. For key claims going into your thesis, spot-check a few citations it marked as passing.

## Long tasks: plan first, then run to completion with `/goal`

For work that touches many files, like revising a whole chapter or tidying a batch of literature notes, have Claude plan first, confirm the plan, then let it run on its own until the acceptance criteria are met. If you haven't worked out what to write yet, have Claude interview you and write an outline first. Steps are in the ["larger pieces of work"](docs/how-it-works.md#大的工作先讓-claude-訪談你) and ["long tasks"](docs/how-it-works.md#長任務先規劃再用-goal-跑到完成) sections of docs/how-it-works.md (Chinese).

## What's in the repo

```
.claude-plugin/            plugin and marketplace manifests
plugin/                    plugin-only hook config and the setup skill
todo/                      /todo side panel (a second, optional plugin)
install.py                 fallback install: install and uninstall
template/                  files shared by both install routes
  .claude/
    hooks/                 five hooks, two shared modules, tests
    skills/dispatch-template/  dispatch prompt templates, model selection table
    agents/verifier.md     the subagent that does acceptance checks
    rules/dispatch-and-verify.md  when to delegate to a subagent, how to verify
    session-log-kit/       session_log injection, writing, and archiving scripts
  hooks-core.json          hook settings install.py merges into settings.json
  hooks-session-log.json   same, for session_log
  hooks-todo.json          same, for --todo
  CLAUDE.md.template       used when creating a new CLAUDE.md
  session_log.md.template, TODO.md.template
docs/
  how-it-works.md          the order things happen in a session, whether to install session_log, how to make your own version
  conventions.md           conventions for file naming, expiry dates, the out folder, and archiving finished files
  vs-superpowers.md        how this differs from Superpowers
tests/test_install.py      tests for install.py (run python tests/test_install.py in the repo folder)
index.html                 intro page
README.md                  this README in Traditional Chinese
README.en.md               this README in English
```

Starting `claude` inside this repo's folder doesn't enable any hooks. Everything sits under `template/` and only takes effect once installed into your project.

## Known limitations

- `rules/` and `dispatch-template` are rules written for Claude to read, and it won't always follow them. Only the hooks enforce anything.
- All hooks fail open: on an error they let the action through so they never block you, but you also get no warning when one breaks. Run the tests after changing a hook.
- `ctrl_char_stop.py` only checks files whose full path appears in the transcript. Paths built from variables inside a command are missed, and on macOS and Linux a path containing spaces is caught only if it's quoted. Files written by a subagent are recorded in a separate transcript and aren't checked either. It blocks at most once per turn.
- Even the built-in `Explore` and `Plan` subagents need `dispatch-template` loaded before they can be dispatched (only `fork` is exempt), so the first dispatch after entering plan mode may be blocked once; after the template loads, it goes through.
- `fork` is exempt from the check and also ignores the `model` parameter: a fork carries the main conversation's full context and uses the main conversation's model. Fork mode is on by default (in the interactive terminal since 2.1.232), and Claude can decide to fork on its own, so "spell it out before delegating" and "pick a model to save quota" don't apply to forks. The rules file says that delegations that need a specific model (haiku batches, an opus second opinion, verifier) shouldn't use fork (official [sub-agents](https://code.claude.com/docs/en/sub-agents#how-forks-differ-from-other-subagents)).
- After the conversation is compacted, `dispatch-template` has to be loaded again before delegating. That covers a manual `/compact`, automatic compaction when the conversation gets too long, and idle compaction. Idle compaction is on by default since 2.1.299: it happens when the conversation is over 200,000 tokens and you've been away for about 54 minutes, so the first delegation after you come back may be blocked once; it goes through after the template loads. After compaction a skill keeps only its first 5,000 tokens, and reloading brings back the full content (official [skills](https://code.claude.com/docs/en/skills#skill-content-lifecycle)).
- The hook scripts and `.claude/settings.json` run automatically every turn, and the install doesn't add deny rules for them. Claude Code already treats `.claude/` as a protected path: in default and acceptEdits modes it always asks before a write, in auto mode a classifier reviews the write, and allow rules in settings can't pre-approve it (official [permission-modes](https://code.claude.com/docs/en/permission-modes#protected-paths)). Adding deny rules on top would also block you from asking Claude to change settings, and block setup from writing protection rules. When Claude wants to change a file under `.claude/`, look at what it's changing before you approve.
- Quota: by default the rules send second opinions and escalations to opus, verifier always runs at `effort: high`, and `/goal` has another model check the condition every turn. These all use more quota. If your quota is small, switch to the downgraded rules in the "額度有限時" (limited quota) section of the rules file; what to do when a dispatch reports that a model is unavailable or the quota is used up is also in the rules file.
- The Python command name the hooks use is set for the environment you install in (often `python` on Windows, `python3` on macOS and Linux). The plugin keeps it in `--config python=`, which you can change with `/plugin configure workflow-kit@workflow-kit`; install.py writes it into `.claude/settings.json`. For a folder opened from two systems, see [Before installing](#before-installing-check-your-environment).
- What's been tested on real hardware: Claude Code itself only on native Windows; the hook and installer tests on Windows and WSL2 (Ubuntu); macOS not yet.
- `--protect` rules can't block a script that opens a file and writes to it itself (see [Protecting raw data](#protecting-raw-data)). If a path contains `*`, `?`, `[`, or `]`, install.py won't write the rule for you; add it by hand.
- Claude Code only. Codex can run the install for you, but it doesn't read `.claude/`: rules go in `AGENTS.md`, skills in `.agents/skills/`, hooks in `.codex/hooks.json`. The dispatch check depends on Claude Code's Skill tool events, and the control-character check reads Claude Code's transcript (Codex's official docs say its transcript format is not a stable interface), so these two hooks can't simply be moved over.
- Everything installed is in Traditional Chinese (see the language note at the top).

## Reporting problems

If it won't install, or a hook blocks something it shouldn't (or misses something it should block), open an [issue](https://github.com/wayhong0928/claude-workflow-template/issues) with your OS and the output of `install.py` or the tests. Issues in English or Chinese are both fine.

## Related resources

All of these are in Traditional Chinese.

| Resource | For whom |
|---|---|
| [mis-thesis-guide](https://wayhong0928.github.io/mis-thesis-guide/) | A knowledge base on research methods and thesis writing, for looking up concepts and criteria |
| [One-hour quickstart](https://wayhong0928.github.io/mis-thesis-guide/pages/ai-quickstart.html) | Using only the ChatGPT, Claude, or Gemini web apps and wanting a thesis assistant set up within an hour (there's also a [Claude Code and Codex version](https://wayhong0928.github.io/mis-thesis-guide/pages/ai-quickstart-agent.html)) |
| [thesis-notes-template](https://github.com/wayhong0928/thesis-notes-template) | Wanting to take literature notes in Obsidian with ready-made templates and filling rules |
| [mis-thesis-skills](https://github.com/wayhong0928/mis-thesis-skills) | Using Claude Code or Codex and wanting the AI to check your topic and writing against fixed criteria |
| [claude-workflow-template](https://github.com/wayhong0928/claude-workflow-template) | Using Claude Code on a thesis or research project and wanting a ready-made workflow setup: session handoff, dispatch templates, independent verification |

## License

MIT, see [LICENSE](LICENSE).
