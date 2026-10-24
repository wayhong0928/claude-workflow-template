import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { PaneData, PaneView, TodoConfig, TodoIndex } from '../types'
import {
  HINT,
  hintData,
  itemsOf,
  paneData,
  projectOf,
  render,
  renderGoals,
  rootsOf,
  splitView,
  summarize,
  summaryText,
  timeView,
  byProject,
  configDirOf,
  type Summary,
} from './view'

// mod 只讀兩個檔，都在設定資料夾（CLAUDE_CONFIG_DIR，沒設就是 ~/.claude）：
// todo.config.json（使用者寫的）與 todo_index.json（scripts/todo_core.py 寫的）。mod 不寫任何檔。
const CONFIG = 'todo.config.json'
const INDEX = 'todo_index.json'

const COMMAND = '/todo'
const PANE = 'todo'
// 預設每個 session 開場自動開；使用者自己關掉就記在 store，之後不再自動開，/todo pane 再打開。
const WANTED = 'paneWanted'
const pane = atom({ plugin: 'todo', key: 'pane' } as const, null)
const isBandHidden = atom({ plugin: 'todo', key: 'isBandHidden' } as const, false)
// 側欄版面，選過的記在 store，下次開 session 沿用。順序就是側欄頂端 1～4 的按鍵。
const VIEW = 'paneView'
const VIEWS: [PaneView, string][] = [['mine', '你'], ['project', '專案'], ['time', '時間'], ['goal', 'Goal']]
const view = atom({ plugin: 'todo', key: 'view' } as const, 'mine' as PaneView)
export const viewOf = (s: unknown): PaneView | undefined =>
  VIEWS.find(([id, label], i) => s === id || s === label || s === String(i + 1))?.[0]
const GROUP_NAME: Record<string, string> = { 你: '你的待辦', Claude: 'Claude 的待辦', 等外部: '等外部', Goal: '已加入 goal 計畫' }
const WHO: Record<string, string> = { 待你決定: '決定', 等外部: '等' }

// 最近一次讀到的 index 與設定；自動完成和輸入框提示只讀這份，不在打字時讀檔。
type Loaded = { index: TodoIndex; at: string | undefined; home: string | undefined }
let loaded: Loaded | null = null
let counts = new Map<string, Summary>()

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'todo',
      description: '列出各專案 TODO 的未勾選項（讀 todo_index.json，不經模型）',
      argumentHint: '[專案名；pane 開側欄；view 1～4 換版面；goal 列 goal 計畫；band 切換輸入框上方的下一步]',
    })
    void reopen($)
    return next(e)
  })

  // 開場的 command hook 跑完 index 之後重讀；/clear 不會再觸發 session.start，改看 source: 'clear'。
  on('classic.SessionStart', async ($, e, next) => {
    const r = await next(e)
    if (e.source === 'clear') await reopen($)
    else await refresh($).catch(() => undefined)
    return r
  }).catch(($, e, next) => next(e))

  // Edit／Write 之後與送出提示之後，plugin 的 command hook 已重產 index，這裡重讀。
  on('classic.PostToolUse', async ($, e, next) => {
    const r = await next(e)
    if (e.tool_name === 'Edit' || e.tool_name === 'Write') await refresh($).catch(() => undefined)
    return r
  }).catch(($, e, next) => next(e))

  on('classic.UserPromptSubmit', async ($, e, next) => {
    const r = await next(e)
    await refresh($).catch(() => undefined)
    return r
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    await refresh($).catch(() => undefined)
    return next(e)
  })

  on('command.run', { command: 'todo' }, async ($, e) => {
    await refresh($).catch(() => undefined)
    const args = (e.args ?? '').trim()
    if (args.toLowerCase() === 'pane') {
      await $.store.set(WANTED, true)
      const opened = await $.ui.open({ id: PANE, title: 'TODO' })
      return { text: opened.isPlaced ? 'TODO 側欄已開（ctrl+x x 關閉，關了之後開場就不再自動開）' : `TODO 側欄還沒顯示：${opened.reason}` }
    }
    const [cmd, arg] = args.split(/\s+/)
    if (cmd?.toLowerCase() === 'view') {
      const v = viewOf(arg)
      if (!v) return { text: `版面有 ${VIEWS.map(([id, l], i) => `${i + 1} ${l}（${id}）`).join('、')}，例如 /todo view 2` }
      await setView($, v)
      return { text: `TODO 側欄改用「${VIEWS.find(x => x[0] === v)![1]}」版面` }
    }
    if (args.toLowerCase() === 'band') {
      const hidden = !(await read($, isBandHidden))
      await update($, isBandHidden, () => hidden)
      return { text: hidden ? '輸入框上方的下一步已收起，/todo band 再打開' : '輸入框上方的下一步已打開' }
    }
    if (!loaded) return { text: HINT }
    if (args.toLowerCase() === 'goal') return { text: renderGoals((await read($, pane))?.goals ?? []) }
    // 沒給專案名時：home 專案列全部，其他專案只列自己的
    const filter = args || (loaded.at && loaded.at !== loaded.home ? loaded.at : '')
    return { text: listAll(loaded.index, today(), filter) }
  })

  on('ui.close', { id: PANE }, async ($, e, next) => {
    if (e.origin.kind === 'person') await $.store.set(WANTED, false)
    return next(e)
  }).catch(($, e, next) => next(e))

  // 輸入框上方一直看得到下一步。
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const d = await read($, pane)
    const n = d?.next
    if (e.props.hasSurvey || !n || n.steps.length === 0 || (await read($, isBandHidden))) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const shown = n.steps.slice(0, 3)
    const more = n.steps.length - shown.length
    return (
      <Box flexDirection="column">
        <Text dimColor wrap="truncate-end">{`下一步｜${n.project}｜${n.title}`}</Text>
        {shown.map((s, i) => (
          <Text key={String(i)} wrap="truncate-end">{`  ${s}`}</Text>
        ))}
        <Box flexDirection="row">
          <Text dimColor>{`${more > 0 ? `還有 ${more} 條，` : ''}全文在 TODO 側欄  `}</Text>
          <Button key="hide" label="收起" onPress={() => update($, isBandHidden, () => true)} />
        </Box>
      </Box>
    )
  })

  // 四種版面，側欄頂端按 1～4 切換（先 ctrl+x tab 把鍵盤交給側欄），也可以打 /todo view <名>。
  // mine：待你決定 → 你 → 下一步 → goal 進度 → 等外部 → Claude。project：各專案全展開。time：照期限。goal：計畫逐步列。
  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const d = await read($, pane)
    if (!d) return <Text dimColor>讀取 TODO 中…</Text>
    if (d.hint) return <Text dimColor>{d.hint}</Text>
    const v = await read($, view)
    // 只列一個專案時不必標專案名
    const where = (p: string) => (d.projects.length > 1 ? `${p}｜` : '')
    // 每條都照 goal 版面的樣子：○ 開頭，有期限的接著標剩幾天，折行時對齊內文
    const row = (key: string, left: number | undefined, text: string, isOneLine = false) => (
      <Box key={key} flexDirection="row">
        <Text dimColor>○ </Text>
        {left !== undefined && <Text color={badgeColor(left)}>{badge(left)}</Text>}
        <Box flexShrink={1}>
          <Text wrap={isOneLine ? 'truncate-end' : undefined}>{text}</Text>
        </Box>
      </Box>
    )
    const head = (key: string, left: number | undefined, text: string) => (
      <Box key={key} flexDirection="row">
        {left !== undefined && <Text color={badgeColor(left)}>{badge(left)}</Text>}
        <Box flexShrink={1}>
          <Text bold>{text}</Text>
        </Box>
      </Box>
    )
    const tabs = (
      <Box flexDirection="row">
        {VIEWS.map(([id, label], i) => (
          <Box key={id} marginRight={1}>
            <Button key={`view-${id}`} label={label} hotkey={String(i + 1)} plain dimColor={v !== id} onPress={() => setView($, id)} />
          </Box>
        ))}
      </Box>
    )

    const mineView = () => {
      const { mine, waiting, claude } = splitView(d.projects)
      return (
        <Box flexDirection="column">
          <Text bold color="claude">{`你要做的（${mine.length}）`}</Text>
          {mine.length === 0 && <Text dimColor>沒有</Text>}
          {mine.map((r, j) => (
            <Box key={`m${j}`} flexDirection="column">
              {(j === 0 || mine[j - 1]!.tag !== r.tag) && (
                <Box marginTop={j === 0 ? 0 : 1}>
                  <Text bold color={r.tag === '待你決定' ? 'warning' : undefined}>{r.tag === '你' ? '待辦' : r.tag}</Text>
                </Box>
              )}
              {row(`r${j}`, r.left, `${where(r.project)}${r.text}`)}
            </Box>
          ))}
          {d.next && d.next.steps.length > 0 && (
            <Box flexDirection="column" marginTop={1}>
              <Text bold color="claude">{`下一步｜${d.next.project}`}</Text>
              <Text dimColor wrap="truncate-end">{d.next.title}</Text>
              {d.next.steps.map((s, j) => row(`n${j}`, undefined, s, true))}
            </Box>
          )}
          {d.goals.map(g => {
            const done = g.sections.reduce((a, s) => a + s.done, 0)
            const total = g.sections.reduce((a, s) => a + s.total, 0)
            return (
              <Box key={g.file} flexDirection="column" marginTop={1}>
                <Text bold color="claude">Goal 計畫</Text>
                {head('title', g.left, g.title)}
                <Text dimColor>{`  已勾 ${done}/${total} 步 · 逐步看按 4`}</Text>
                {g.next && <Text wrap="truncate-end">{`  接著做：${g.next}`}</Text>}
              </Box>
            )
          })}
          {waiting.total > 0 && (
            <Box flexDirection="column" marginTop={1}>
              <Text bold color="claude">{`等外部（${waiting.total}）`}</Text>
              {waiting.soon.map((r, j) => row(`w${j}`, r.left, `${where(r.project)}${r.text}`))}
            </Box>
          )}
          {claude.total > 0 && (
            <Box flexDirection="column" marginTop={1}>
              <Text bold color="claude">{`Claude 的待辦（${claude.total}）`}</Text>
              {claude.soon.map((r, j) => row(`c${j}`, r.left, `${where(r.project)}${r.text}`))}
              <Text dimColor>{claude.counts.map(c => `${c.project} ${c.n}`).join(' · ')}</Text>
              <Text dimColor>全部展開按 2</Text>
            </Box>
          )}
        </Box>
      )
    }

    const projectView = () => {
      const all = byProject(d.projects, d.goals)
      return (
        <Box flexDirection="column">
          {all.length === 0 && <Text dimColor>沒有未完成的條目</Text>}
          {all.map((p, k) => (
            <Box key={p.name} flexDirection="column" marginTop={k === 0 ? 0 : 2}>
              <Text bold color="claude">{`■ ${p.name}（${p.groups.reduce((n, g) => n + g.rows.length, 0)}）`}</Text>
              {p.groups.map(g => (
                <Box key={g.tag} flexDirection="column" marginTop={1}>
                  <Text bold color={g.tag === '待你決定' ? 'warning' : g.tag === 'Goal' ? 'success' : undefined}>{`${GROUP_NAME[g.tag] ?? g.tag} ${g.rows.length}`}</Text>
                  {g.rows.map((r, j) => row(`${g.tag}${j}`, r.left, r.text))}
                </Box>
              ))}
            </Box>
          ))}
        </Box>
      )
    }

    const timeline = () => {
      const t = timeView(d.projects, d.goals)
      return (
        <Box flexDirection="column">
          {t.buckets.length === 0 && <Text dimColor>沒有帶期限的條目</Text>}
          {t.buckets.map((b, k) => (
            <Box key={b.name} flexDirection="column" marginTop={k === 0 ? 0 : 1}>
              <Text bold color={b.name === '已過期' ? 'error' : 'claude'}>{`${b.name}（${b.rows.length}）`}</Text>
              {b.rows.map((r, j) => row(`${b.name}${j}`, r.left, `${WHO[r.tag] ?? r.tag}｜${where(r.project)}${r.text}`))}
            </Box>
          ))}
          <Box marginTop={1}>
            <Text dimColor>{`沒期限的：你 ${t.undated.mine} 條（按 1）、Claude ${t.undated.claude} 條（按 2）`}</Text>
          </Box>
        </Box>
      )
    }

    const goalView = () => (
      <Box flexDirection="column">
        {d.goals.length === 0 && <Text dimColor>沒有進行中的 goal 計畫</Text>}
        {d.goals.map(g => (
          <Box key={g.file} flexDirection="column">
            {head('title', g.left, g.title)}
            {g.sections.map(s => (
              <Box key={s.name} flexDirection="column" marginTop={1}>
                <Text bold color={s.done === s.total ? 'success' : 'claude'} wrap="truncate-end">{`${s.name}  ${s.done}/${s.total}`}</Text>
                {(s.steps ?? []).map((st, j) => (
                  <Text key={String(j)} dimColor={st.isDone} wrap="truncate-end">{`${st.isDone ? '✓' : '○'} ${st.text}`}</Text>
                ))}
              </Box>
            ))}
            {g.todos.length > 0 && (
              <Box flexDirection="column" marginTop={1}>
                <Text bold color="claude">{`併入的待辦（${g.todos.length}）`}</Text>
                {g.todos.map((t, j) => row(`t${j}`, t.left, `${where(t.project)}${t.text}`))}
              </Box>
            )}
          </Box>
        ))}
      </Box>
    )

    const body = v === 'project' ? projectView() : v === 'time' ? timeline() : v === 'goal' ? goalView() : mineView()
    return (
      <Box flexDirection="column">
        {tabs}
        <Box marginTop={1} flexDirection="column">
          {body}
        </Box>
        <Box marginTop={1}>
          <Text dimColor>{`${d.date} 更新 · ctrl+x tab 後按 1～4 換版面，方向鍵捲動`}</Text>
        </Box>
      </Box>
    )
  })

  // 打 `/todo c` 時列出名稱含 c 的專案，旁邊附未完成條數。
  on('prompt.autocomplete', async ($, e, next) => {
    const r = await next(e)
    const mine = suggest(e.text, e.start, e.token, counts)
    return mine.length ? { suggestions: [...r.suggestions, ...mine] } : r
  })

  // 輸入框只有 `/todo` 時，在後面淡淡顯示總計，不進草稿。
  on('prompt.edit', async ($, e, next) => {
    const r = await next(e)
    const hint = hintFor(r.text, r.cursor, counts)
    if (!hint) return r
    const at = r.text.length
    return { ...r, decorations: [...(r.decorations ?? []), { start: at, end: at, virtualText: hint, dimColor: true }] }
  })
}

// 有期限的條目標剩幾天。
const badge = (left: number) => (left < 0 ? `過${-left}天 ` : `剩${left}天 `)
const badgeColor = (left: number) => (left < 0 ? 'error' : left <= 2 ? 'warning' : undefined)

function today(): Date {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}

const blank = (v: string | undefined) => v || undefined

// 讀設定檔與 index。任一個讀不到或不是 JSON 就回 null，側欄只顯示一行提示。
export async function load($: EngineInterface): Promise<Loaded | null> {
  // env.get 的名稱要寫字面值，validate 才列得出 mod 讀了哪些環境變數
  const configDir = blank(await $.env.get('CLAUDE_CONFIG_DIR').catch(() => undefined))
  const home = blank(await $.env.get('HOME').catch(() => undefined)) ?? blank(await $.env.get('USERPROFILE').catch(() => undefined))
  const isWsl = Boolean(await $.env.get('WSL_DISTRO_NAME').catch(() => undefined))
  const dir = configDirOf({ configDir, home })
  if (!dir) return null
  const conf = await readJson<TodoConfig>($, `${dir}/${CONFIG}`)
  const index = await readJson<TodoIndex>($, `${dir}/${INDEX}`)
  if (!conf || !index || !Array.isArray(index.projects)) return null
  const at = projectOf(await $.session.cwd().catch(() => ''), rootsOf(conf, { home, isWsl }))
  return { index, at, home: conf.home ?? index.home ?? index.projects[0]?.name }
}

async function readJson<T>($: EngineInterface, path: string): Promise<T | null> {
  const text = await $.fs.read(path).catch(() => undefined)
  if (typeof text !== 'string') return null
  try {
    return JSON.parse(text) as T
  } catch {
    return null
  }
}

export function dataOf(l: Loaded | null, t: Date, now: Date): PaneData {
  return l ? paneData(l.index, t, l.at, l.home, now) : hintData(now)
}

async function refresh($: EngineInterface) {
  loaded = await load($)
  const t = today()
  counts = loaded ? countsOf(loaded.index, t) : new Map()
  await update($, pane, () => dataOf(loaded, t, new Date()))
}

// 開場和 /clear 後：重讀 index，使用者沒手動關過側欄就打開。
// 自動開不算使用者要求，終端機太窄時引擎先不畫（還沒接上畫面的 no-surface 除外），用 toast 提示怎麼叫出來。
async function reopen($: EngineInterface) {
  await refresh($).catch(() => undefined)
  const v = viewOf(await $.store.get(VIEW).catch(() => undefined))
  if (v) await update($, view, () => v)
  if ((await $.store.get(WANTED)) === false) return
  const opened = await $.ui.open({ id: PANE, title: 'TODO' }).catch(() => undefined)
  if (opened && !opened.isPlaced && !opened.reason.startsWith('no-surface')) {
    $.ui.toast(`TODO 側欄還沒顯示（${opened.reason}），打 /todo pane 可直接打開`)
  }
}

async function setView($: EngineInterface, v: PaneView) {
  await update($, view, () => v)
  await $.store.set(VIEW, v)
}

export function suggest(text: string, start: number, token: string, c: Map<string, Summary>) {
  if (!text.startsWith(COMMAND + ' ') || start <= COMMAND.length) return []
  const want = token.toLowerCase()
  return [...c.keys()].filter(name => name.toLowerCase().includes(want)).map(name => {
    const s = c.get(name)
    return s ? { text: name, description: summaryText(s) } : { text: name }
  })
}

export function hintFor(text: string, cursor: number, c: Map<string, Summary>): string | undefined {
  if (text.trimEnd() !== COMMAND || cursor !== text.length || c.size === 0) return undefined
  const all = { total: 0, overdue: 0, soon: 0 }
  for (const s of c.values()) {
    all.total += s.total
    all.overdue += s.overdue
    all.soon += s.soon
  }
  return (text.endsWith(' ') ? ' ' : '  ') + summaryText(all)
}

export function countsOf(index: TodoIndex, t: Date): Map<string, Summary> {
  return new Map(index.projects.map(p => [p.name, summarize(itemsOf(p.items), t)]))
}

export function listAll(index: TodoIndex, t: Date, filter: string): string {
  const want = filter.trim().toLowerCase()
  const blocks: string[] = []
  let total = 0
  for (const p of index.projects) {
    if (want && !p.name.toLowerCase().includes(want)) continue
    const items = itemsOf(p.items)
    if (items.length === 0) continue
    total += items.length
    blocks.push(render(p.name, items, t).join('\n'))
  }
  if (blocks.length === 0) return want ? `沒有符合「${filter.trim()}」的專案，或它沒有未完成項目。` : '所有專案都沒有未完成項目。'
  const head = `TODO 全部未完成 ${total} 條（${t.getFullYear()}-${t.getMonth() + 1}-${t.getDate()}）`
  return [head, ...blocks].join('\n\n')
}
