import type { PromptAutocompleteInput, PromptAutocompleteResult, PromptEditInput, PromptEditResult } from 'claude-code'
import { expect, test } from 'claude-code/testing'

import type { IndexGoal, IndexItem, IndexProject, TodoIndex } from '../types'
import { HINT, byProject, configDirOf, goalsOf, itemsOf, nextOf, paneData, projectOf, render, renderGoals, resolveRoot, rootsOf, splitView, summarize, timeView } from './view'
import { countsOf, hintFor, listAll, suggest, viewOf } from './register'

// 解析在 scripts/todo_core.py（有自己的 unittest）；這裡只測「給 index、看畫面」。
const today = new Date(2026, 9, 18)

const item = (who: string, text: string, more: Partial<IndexItem> = {}): IndexItem => ({
  who, text, due: null, born: null, touched: null, stale: false, merged: false, goal: null, file: 'TODO.md', line: 1, ...more,
})
const project = (name: string, items: IndexItem[], more: Partial<IndexProject> = {}): IndexProject => ({
  name, root: `/home/u/projects/${name}`, todo: ['TODO.md'], log: null, items, next: null, ...more,
})
const index = (projects: IndexProject[], goals: IndexGoal[] = [], home: string | null = 'notes'): TodoIndex => ({
  version: 1, generated: '2026-10-18T00:00:00', today: '2026-10-18', config: null, home, dueSoonDays: 7,
  projects, goals, expiring: [], problems: [],
})
const PLAN: IndexGoal = {
  id: '/home/u/projects/notes/計畫_甲.md', project: 'notes', file: '計畫_甲.md', path: '/home/u/projects/notes/計畫_甲.md',
  title: '甲計畫', due: '2026-10-24',
  sections: [{ name: 'G1 第一節', done: 1, total: 2, steps: [{ text: '1. 做完的', isDone: true }, { text: '2. 還沒做的', isDone: false }] }],
  next: 'G1 第一節｜2. 還沒做的',
}

test('/todo 文字清單依「誰」分組，有期限的在前，標剩幾天與待驗現況', () => {
  const items = itemsOf([
    item('你', '甲', { due: '2026-10-18', born: '2026-10-13' }),
    item('Claude', '乙', { born: '2026-09-27', stale: true }),
    item('未分類', '沒標籤的丙'),
  ])
  expect(items.map(i => i.tag)).toEqual(['你', 'Claude', '未分類'])
  const out = render('測試', items, today).join('\n')
  expect(out).toContain('【測試】未完成 3 條')
  expect(out).toContain('甲（期限 10-18）［剩 0 天］')
  expect(out).toContain('乙［待驗現況］')
  expect(out).toContain('〔未分類〕')
})

test('index 裡不認得的 who 歸未分類', () => {
  expect(itemsOf([item('工作身分', '甲')])[0]!.tag).toBe('未分類')
})

const IDX = index([project('notes', [item('你', '日常甲'), item('Claude', '日常乙')]), project('thesis', [item('你', '論文甲')]), project('空', [])])

test('listAll 列出所有有條目的專案，專案名可篩選', () => {
  const all = listAll(IDX, today, '')
  expect(all).toContain('TODO 全部未完成 3 條')
  expect(all).toContain('【notes】未完成 2 條')
  expect(all).toContain('【thesis】未完成 1 條')
  expect(all).not.toContain('【空】')
  const one = listAll(IDX, today, ' THESIS ')
  expect(one).toContain('【thesis】')
  expect(one).not.toContain('【notes】')
  expect(listAll(IDX, today, '沒這專案')).toContain('沒有符合')
})

test('/todo 由 mod 自己回答，回傳文字（沒有設定檔時回提示）', async $ => {
  const ran = await $.command.run({ command: 'todo', args: '', origin: { kind: 'plugin', name: 'todo' } } as Parameters<typeof $.command.run>[0])
  expect(typeof ran.text).toBe('string')
})

test('summarize 算已過期與 7 天內到期', () => {
  const items = itemsOf([item('你', '甲', { due: '2026-10-17' }), item('你', '乙', { due: '2026-10-25' }), item('你', '丙', { due: '2026-11-30' }), item('你', '丁')])
  expect(summarize(items, today)).toEqual({ total: 4, overdue: 1, soon: 1 })
})

test('自動完成只在 /todo 的參數位置出現，依名稱篩選並附條數', () => {
  const c = countsOf(IDX, today)
  expect(suggest('/todo th', 6, 'th', c)).toEqual([{ text: 'thesis', description: '未完成 1 條' }])
  expect(suggest('/todo no', 6, 'no', c).map(r => r.text)).toEqual(['notes'])
  expect(suggest('/todo', 0, '/todo', c)).toEqual([])
  expect(suggest('thesis', 0, 'thesis', c)).toEqual([])
})

test('輸入框只有 /todo 時顯示總計提示，其他情況不顯示', () => {
  const c = countsOf(IDX, today)
  expect(hintFor('/todo', 5, c)).toBe('  未完成 3 條')
  expect(hintFor('/todo ', 6, c)).toBe(' 未完成 3 條')
  expect(hintFor('/todo thesis', 12, c)).toBe(undefined)
  expect(hintFor('/todo', 2, c)).toBe(undefined)
  expect(hintFor('/todo', 5, new Map())).toBe(undefined)
})

test('prompt.autocomplete 與 prompt.edit 掛上後不弄壞引擎的結果', async ($, on) => {
  // 測試環境沒有引擎底層，用 on 當底層：自動完成沒有列，編輯照做 splice
  on('prompt.autocomplete', async () => ({ suggestions: [{ text: 'engine' }] }))
  on('prompt.edit', async (_$, e) => {
    const text = e.text.slice(0, e.start) + e.inputText + e.text.slice(e.end)
    return { text, cursor: e.start + e.inputText.length }
  })
  // 型別檔的測試 $ 沒列這兩個事件，執行期有；轉型只為了讓 tsc 過
  const prompt = $.prompt as unknown as {
    autocomplete: (e: PromptAutocompleteInput) => Promise<PromptAutocompleteResult>
    edit: (e: PromptEditInput) => Promise<PromptEditResult>
  }
  const ac = await prompt.autocomplete({ text: 'hello', cursor: 5, token: 'hello', start: 0 })
  expect(ac.suggestions).toEqual([{ text: 'engine' }])
  const ed = await prompt.edit({ origin: { kind: 'composer' }, text: 'hell', cursor: 4, start: 4, end: 4, inputText: 'o' })
  expect(ed.text).toBe('hello')
})

test('home 專案與不在專案底下：列全部有條目的專案，所在專案排第一，依「誰」分組、有期限的在前', () => {
  const idx = index([
    project('thesis', [item('你', '快到', { due: '2026-10-20' })]),
    project('notes', [item('Claude', '沒期限'), item('你', '也沒期限'), item('你', '過期', { due: '2026-10-17' })]),
    project('空', []),
  ])
  const d = paneData(idx, today, 'notes', 'notes')
  expect(d.projects.map(p => p.name)).toEqual(['notes', 'thesis'])
  expect(d.projects[0]).toEqual({
    name: 'notes', total: 3, overdue: 1, soon: 0,
    groups: [
      { tag: '你', rows: [{ text: '過期', left: -1 }, { text: '也沒期限' }] },
      { tag: 'Claude', rows: [{ text: '沒期限' }] },
    ],
  })
  expect(d.projects[1]!.groups[0]!.rows).toEqual([{ text: '快到', left: 2 }])
  expect(paneData(idx, today, undefined, 'notes').projects.map(p => p.name)).toEqual(['thesis', 'notes'])
  expect(d.date).toBe('10/18 00:00')
  expect(paneData(index([]), today, 'notes', 'notes', new Date(2026, 9, 3, 9, 5)).date).toBe('10/03 09:05')
})

test('其他專案只列自己的，沒有條目也照樣顯示', () => {
  const b = [item('你', '快到', { due: '2026-10-20' })]
  expect(paneData(index([project('notes', b), project('thesis', b)]), today, 'thesis', 'notes').projects.map(p => p.name)).toEqual(['thesis'])
  const empty = paneData(index([project('notes', b), project('side', [])]), today, 'side', 'notes')
  expect(empty.projects).toEqual([{ name: 'side', total: 0, overdue: 0, soon: 0, groups: [] }])
})

test('依 session 所在資料夾判斷專案，子資料夾也算，大小寫與斜線不拘，多個符合取最深的', () => {
  const roots: [string, string][] = [['notes', 'C:/Users/u/projects/notes'], ['site', 'C:/Users/u/projects/site'], ['all', 'C:/Users/u/projects']]
  expect(projectOf('C:\\Users\\u\\projects\\notes', roots)).toBe('notes')
  expect(projectOf('c:/users/u/projects/notes/sub/', roots)).toBe('notes')
  expect(projectOf('C:\\Users\\u\\projects\\site-old', roots)).toBe('all')
  expect(projectOf('C:\\Users\\u', roots)).toBe(undefined)
  expect(projectOf('', roots)).toBe(undefined)
})

test('設定檔的 root 展開 ~，WSL 裡把磁碟代號換成 wslPrefix', () => {
  expect(resolveRoot('~/projects/notes', { home: 'C:\\Users\\u' })).toBe('C:/Users/u/projects/notes')
  expect(resolveRoot('E:\\work\\notes', { isWsl: true })).toBe('/mnt/e/work/notes')
  expect(resolveRoot('E:/work', { isWsl: true }, '/mnt/d')).toBe('/mnt/e/work')
  expect(resolveRoot('E:/work', {})).toBe('E:/work')
  expect(rootsOf({ projects: [{ name: 'a', root: '~/a' }] }, { home: '/home/u' })).toEqual([['a', '/home/u/a']])
  expect(configDirOf({ configDir: 'C:\\cfg\\' })).toBe('C:/cfg')
  expect(configDirOf({ home: '/home/u' })).toBe('/home/u/.claude')
  expect(configDirOf({})).toBe(undefined)
})

test('[你決定] 顯示成「待你決定」，排在「你」前面', () => {
  const items = itemsOf([item('你', '英文課上完回報'), item('你決定', '要不要改題目'), item('Claude', '研究')])
  expect(items.map(i => i.tag)).toEqual(['你', '待你決定', 'Claude'])
  const out = render('測試', items, today).join('\n')
  expect(out.indexOf('〔待你決定〕')).toBeLessThan(out.indexOf('〔你〕'))
})

const NEXT = { title: '2026-10-19（晚上） | 新的一筆', steps: ['使用者：回五項決定', 'Claude：改設定'] }

test('沒有 session_log 的專案，下一步看 home 專案的', () => {
  const idx = index([project('notes', [], { log: '/home/u/projects/notes/session_log.md', next: NEXT }), project('site', []), project('thesis', [], { log: 'x', next: null })])
  expect(nextOf(idx, 'site', 'notes')?.project).toBe('notes')
  expect(nextOf(idx, undefined, 'notes')?.steps.length).toBe(2)
  expect(nextOf(idx, 'thesis', 'notes')).toBe(null)
})

// /clear 不觸發 session.start，側欄要靠 classic.SessionStart 的 source: 'clear' 重開。
test('/clear 之後重開 TODO 側欄，其他來源不重開', async ($, on) => {
  const opened: string[] = []
  on('classic.SessionStart', async () => ({}))
  on('store.get', async () => ({ value: undefined }))
  on('ui.open', async (_$, e) => {
    opened.push(e.id)
    return { value: { isPlaced: true as const } }
  })
  await $.classic.SessionStart({ source: 'compact' })
  expect(opened).toEqual([])
  await $.classic.SessionStart({ source: 'clear' })
  expect(opened).toEqual(['todo'])
})

test('goal 計畫：index 給的期限換成剩幾天；其他專案只看跟自己有關的', () => {
  const goals = goalsOf(index([], [PLAN, { ...PLAN, id: 'b', title: '乙', file: '計畫_乙.md', due: null, next: null }]), today)
  expect(goals.map(g => [g.title, g.left])).toEqual([['甲計畫', 6], ['乙', undefined]])
  const idx = index([project('notes', []), project('thesis', [])], [PLAN])
  expect(paneData(idx, today, 'thesis', 'notes').goals).toEqual([])
  expect(paneData(idx, today, 'notes', 'notes').goals.length).toBe(1)
  const text = renderGoals(goals)
  expect(text).toContain('【notes】甲計畫［剩 6 天］')
  expect(text).toContain('  1/2  G1 第一節')
  expect(text).toContain('  接著做：G1 第一節｜2. 還沒做的')
  expect(renderGoals([])).toContain('沒有進行中的 goal 計畫')
})

test('併進 goal 計畫的條目從各專案拿掉、列在計畫底下；計畫本身那條不重複列；其他專案 session 也看得到自己併入的計畫', () => {
  const g = PLAN.id
  const notes = [
    item('Claude', '甲計畫：照計畫跑', { goal: g, due: '2026-10-24' }),
    item('Claude', '精簡測試', { goal: g, merged: true, due: '2026-10-24' }),
    item('Claude', '舊寫法', { goal: g, merged: true }),
    item('Claude', '併入別的 goal 計畫不算', { merged: true }),
    item('你', '沒併入的照列'),
  ]
  const idx = index([project('notes', notes), project('thesis', [item('Claude', '統計計畫定稿', { goal: g, merged: true })])], [PLAN])
  const all = paneData(idx, today, 'notes', 'notes')
  expect(all.goals[0]!.todos).toEqual([
    { project: 'notes', text: '精簡測試', left: 6 },
    { project: 'notes', text: '舊寫法' },
    { project: 'thesis', text: '統計計畫定稿' },
  ])
  expect(all.goals[0]!.from).toEqual(['notes', 'thesis'])
  expect(all.projects.map(p => [p.name, p.total])).toEqual([['notes', 2]])
  expect(all.projects[0]!.groups.flatMap(x => x.rows.map(r => r.text))).toEqual(['沒併入的照列', '併入別的 goal 計畫不算'])
  const inThesis = paneData(idx, today, 'thesis', 'notes')
  expect(inThesis.goals.length).toBe(1)
  expect(inThesis.projects).toEqual([{ name: 'thesis', total: 0, overdue: 0, soon: 0, groups: [] }])
  expect(paneData(index([project('side', [])], [PLAN]), today, 'side', 'notes').goals).toEqual([])
  expect(renderGoals(all.goals)).toContain('  併入的待辦 3 條\n  - notes｜精簡測試')
  // 計畫做完（index 不再列它）時，條目回到各專案
  expect(paneData(index([project('thesis', [item('Claude', '統計計畫定稿', { goal: 'gone', merged: true })])]), today, 'thesis', 'notes').projects[0]!.total).toBe(1)
})

test('pane 版面：你要做的跨專案集中、照組別與期限排；等外部與 Claude 的只留條數與 7 天內到期', () => {
  const idx = index([
    project('notes', [item('Claude', '長期'), item('你', '沒期限'), item('Claude', '快到', { due: '2026-10-20' }), item('Claude', '還早', { due: '2026-11-30' })]),
    project('thesis', [item('你決定', '要不要改題目'), item('等外部', '等資料', { due: '2026-10-21' }), item('等外部', '等很久'), item('你', '繳交', { due: '2026-10-19' }), item('未分類', '沒標籤')]),
  ])
  const { mine, waiting, claude } = splitView(paneData(idx, today, 'notes', 'notes').projects)
  expect(mine.map(r => `${r.tag}/${r.project}/${r.text}`)).toEqual(['待你決定/thesis/要不要改題目', '你/thesis/繳交', '你/notes/沒期限'])
  expect(waiting.total).toBe(2)
  expect(waiting.soon).toEqual([{ project: 'thesis', text: '等資料', left: 3 }])
  expect(claude.total).toBe(4)
  expect(claude.counts).toEqual([{ project: 'notes', n: 3 }, { project: 'thesis', n: 1 }])
  expect(claude.soon).toEqual([{ project: 'notes', text: '快到', left: 2 }])
})

test('時間版面：帶期限的跨專案照剩幾天分三段，goal 計畫補回來；沒期限的只算條數', () => {
  const projects = [
    { name: 'notes', total: 3, overdue: 1, soon: 0, groups: [
      { tag: '你', rows: [{ text: '過期', left: -1 }, { text: '沒期限' }] },
      { tag: 'Claude', rows: [{ text: '很久以後', left: 30 }, { text: '沒期限乙' }] },
    ] },
    { name: 'thesis', total: 1, overdue: 0, soon: 1, groups: [{ tag: '待你決定', rows: [{ text: '要不要', left: 3 }] }] },
  ]
  const goals = [{ project: 'notes', title: '計畫甲', file: '計畫_甲.md', left: 2, sections: [], from: [], todos: [{ project: 'thesis', text: '併入的', left: 5 }] }]
  const t = timeView(projects, goals)
  expect(t.buckets.map(b => [b.name, b.rows.map(r => `${r.tag}/${r.project}/${r.text}`)])).toEqual([
    ['已過期', ['你/notes/過期']],
    ['7 天內', ['Goal/notes/計畫甲', '待你決定/thesis/要不要', 'Goal/thesis/併入的']],
    ['之後', ['Claude/notes/很久以後']],
  ])
  expect(t.undated).toEqual({ mine: 1, claude: 1 })
})

test('/todo view 認得代號、按鍵數字和中文名', () => {
  expect(viewOf('project')).toBe('project')
  expect(viewOf('3')).toBe('time')
  expect(viewOf('Goal')).toBe('goal')
  expect(viewOf('你')).toBe('mine')
  expect(viewOf('亂打')).toBe(undefined)
  expect(viewOf(undefined)).toBe(undefined)
})

test('專案版面：已加入 goal 計畫的排在各專案最後一組，條目全併進計畫的專案也列出', () => {
  const projects = [{ name: 'notes', total: 1, overdue: 0, soon: 0, groups: [{ tag: '你', rows: [{ text: '甲' }] }] }]
  const goals = [{ project: 'notes', title: '計畫甲', file: '計畫_甲.md', left: 2, sections: [], from: [], todos: [{ project: 'thesis', text: '併入的', left: 5 }] }]
  expect(byProject(projects, goals).map(p => [p.name, p.groups.map(g => `${g.tag}:${g.rows.map(r => r.text).join('/')}`)])).toEqual([
    ['notes', ['你:甲', 'Goal:計畫：計畫甲']],
    ['thesis', ['Goal:併入的']],
  ])
})

// ---- 掛上引擎：mod 只讀設定資料夾裡的 todo.config.json 與 todo_index.json ----

const PANE_PROPS = { title: 'TODO', isFocused: true, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 40 }, view: {} } as const

test('側欄四種版面：按 2 全展開各專案、按 3 照期限、按 4 逐步列 goal 計畫', async ($, on) => {
  const read: string[] = []
  const files: Record<string, string> = {
    '/cfg/todo.config.json': JSON.stringify({ home: 'notes', projects: [{ name: 'notes', root: '~/projects/notes', todo: ['TODO.md'] }] }),
    '/cfg/todo_index.json': JSON.stringify(index([
      project('notes', [
        item('你決定', '要不要換版面'),
        item('Claude', '研究甲', { due: '2026-10-30' }),
        item('Claude', '研究乙'),
        item('Claude', '照計畫跑', { goal: PLAN.id, due: '2026-10-24' }),
      ]),
    ], [PLAN])),
  }
  on('fs.read', async (_$, e) => {
    // 引擎把路徑轉成所在平台的絕對路徑（Windows 會補磁碟代號、換反斜線），只比對結尾
    const p = e.path.split(String.fromCharCode(92)).join('/')
    read.push(p)
    const hit = Object.keys(files).find(k => p.endsWith(k))
    if (!hit) throw new Error('not found')
    return { value: files[hit]! }
  })
  on('env.get', async (_$, e) => ({ value: e.name === 'CLAUDE_CONFIG_DIR' ? '/cfg' : e.name === 'HOME' ? '/home/u' : undefined }))
  on('session.cwd', async () => ({ value: '/home/u/projects/notes' }))
  on('store.get', async () => ({ value: undefined }))
  on('store.set', async () => ({ value: undefined }))
  on('command.register', async () => ({ value: { command: 'todo' } }))
  on('ui.open', async () => ({ value: { isPlaced: true as const } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/home/u/projects/notes', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'todo', component: 'Pane', requestId: 'todo', surface: 'terminal', props: PANE_PROPS })
  expect((await ui.find({ type: 'Text', text: /你要做的/ }))?.text).toBe('你要做的（1）')
  expect((await ui.find({ type: 'Text', text: '待你決定' }))).toBeTruthy()
  await ui.press({ key: 'view-project' })
  expect((await ui.find({ type: 'Text', text: /Claude 的待辦/ }))?.text).toBe('Claude 的待辦 2')
  expect(await ui.find({ type: 'Text', text: /研究乙/ })).toBeTruthy()
  expect((await ui.find({ type: 'Text', text: /^■ / }))?.text).toBe('■ notes（4）')
  expect(await ui.find({ type: 'Text', text: '○ ' })).toBeTruthy()
  expect((await ui.find({ type: 'Text', text: /已加入 goal 計畫/ }))?.text).toBe('已加入 goal 計畫 1')
  expect(await ui.find({ type: 'Text', text: '計畫：甲計畫' })).toBeTruthy()
  await ui.press({ key: 'view-time' })
  expect(await ui.find({ type: 'Text', text: /Goal｜甲計畫/ })).toBeTruthy()
  await ui.press({ key: 'view-goal' })
  expect((await ui.find({ type: 'Text', text: /G1 第一節/ }))?.text).toBe('G1 第一節  1/2')
  expect((await ui.find({ type: 'Text', text: /還沒做的/ }))?.text).toBe('○ 2. 還沒做的')
  await ui.unmount()
  // 只讀設定資料夾裡的兩個檔，不讀 TODO 或計畫檔本身
  expect(read.length > 0 && read.every(p => p.endsWith('/cfg/todo.config.json') || p.endsWith('/cfg/todo_index.json'))).toBe(true)
})

// command hook 重產 index 之後重讀；不是 Edit／Write 的工具不重讀。
test('只有 Edit／Write 之後重讀 index', async ($, on) => {
  let reads = 0
  on('fs.read', async () => {
    reads++
    throw new Error('not found')
  })
  on('env.get', async (_$, e) => ({ value: e.name === 'HOME' ? '/home/u' : undefined }))
  on('classic.PostToolUse', async () => ({}))
  const call = (tool_name: string) =>
    $.classic.PostToolUse({ tool_name, tool_input: {}, tool_response: {}, tool_use_id: 't' } as unknown as Parameters<typeof $.classic.PostToolUse>[0])
  await call('Read')
  expect(reads).toBe(0)
  await call('Edit')
  expect(reads).toBeGreaterThan(0)
})

test('沒有設定檔時側欄只顯示一行提示，不報錯', async ($, on) => {
  on('fs.read', async () => {
    throw new Error('not found')
  })
  on('env.get', async (_$, e) => ({ value: e.name === 'HOME' ? '/home/u' : undefined }))
  on('session.cwd', async () => ({ value: '/home/u' }))
  on('store.get', async () => ({ value: undefined }))
  on('store.set', async () => ({ value: undefined }))
  on('command.register', async () => ({ value: { command: 'todo' } }))
  on('ui.open', async () => ({ value: { isPlaced: true as const } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/home/u', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'todo', component: 'Pane', requestId: 'todo', surface: 'terminal', props: PANE_PROPS })
  expect((await ui.find({ type: 'Text', text: /todo\.config\.json/ }))?.text).toBe(HINT)
  expect(await ui.find({ type: 'Text', text: /你要做的/ })).toBe(undefined)
  await ui.unmount()
  const ran = await $.command.run({ command: 'todo', args: '', origin: { kind: 'plugin', name: 'todo' } } as Parameters<typeof $.command.run>[0])
  expect(ran.text).toBe(HINT)
})
