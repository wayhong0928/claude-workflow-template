// 畫面用的排序與分組。解析全在 scripts/todo_core.py，這裡只吃它寫的 todo_index.json。
import type {
  GoalPlan,
  GoalTodo,
  IndexItem,
  NextStep,
  PaneData,
  PaneProject,
  PaneRow,
  TodoConfig,
  TodoIndex,
} from '../types'

export type Item = { tag: string; text: string; due?: Date; stale: boolean; goal: string | null; merged: boolean }

// [你決定] 在畫面上叫「待你決定」，排最前面。
export const GROUPS = ['待你決定', '你', '等外部', 'Claude', '未分類']
const TAG_OF: Record<string, string> = { 你決定: '待你決定' }
export const SOON_DAYS = 7
const DAY = 86_400_000

export const HINT = 'TODO 還沒設定：打 /workflow-kit:setup，或照 todo/README.md 手寫 todo.config.json'

export const days = (a: Date, b: Date) => Math.round((a.getTime() - b.getTime()) / DAY)

export function dateOf(s: string | null | undefined): Date | undefined {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s ?? '')
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : undefined
}

// 側欄頁尾的更新時間，例如 10/22 09:05。
const pad = (n: number) => String(n).padStart(2, '0')
export const stamp = (d: Date) => `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`

export function itemsOf(items: IndexItem[]): Item[] {
  return items.map(i => {
    const due = dateOf(i.due)
    const it: Item = { tag: TAG_OF[i.who] ?? (GROUPS.includes(i.who) ? i.who : '未分類'), text: i.text, stale: i.stale, goal: i.goal, merged: i.merged }
    if (due) it.due = due
    return it
  })
}

export type Summary = { total: number; overdue: number; soon: number }

// 給自動完成和輸入框提示用的計數：已過期、7 天內到期、總數。
export function summarize(items: Item[], today: Date): Summary {
  let overdue = 0
  let soon = 0
  for (const i of items) {
    if (!i.due) continue
    const left = days(i.due, today)
    if (left < 0) overdue++
    else if (left <= SOON_DAYS) soon++
  }
  return { total: items.length, overdue, soon }
}

export function summaryText(s: Summary): string {
  const parts = [`未完成 ${s.total} 條`]
  if (s.overdue) parts.push(`已過期 ${s.overdue}`)
  if (s.soon) parts.push(`7 天內到期 ${s.soon}`)
  return parts.join(' · ')
}

const mmdd = (d: Date) => `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

// /todo 的文字清單：依「誰」分組，有期限的排前面。
export function render(name: string, items: Item[], today: Date): string[] {
  const out = [`【${name}】未完成 ${items.length} 條`]
  for (const g of GROUPS) {
    const group = items.filter(i => i.tag === g)
    if (group.length === 0) continue
    const dated = group.filter(i => i.due).sort((a, b) => a.due!.getTime() - b.due!.getTime())
    out.push(`  〔${g}〕`)
    for (const i of [...dated, ...group.filter(i => !i.due)]) {
      let mark = ''
      if (i.due) {
        const left = days(i.due, today)
        mark = `（期限 ${mmdd(i.due)}）` + (left < 0 ? `［已過期 ${-left} 天］` : `［剩 ${left} 天］`)
      } else if (i.stale) {
        mark = '［待驗現況］'
      }
      out.push(`  - ${i.text}${mark}`)
    }
  }
  return out
}

// 一組裡有期限的在前（近的在前），其餘照檔內順序。
function rowsOf(items: Item[], today: Date): PaneRow[] {
  const dated = items.filter(i => i.due).sort((a, b) => a.due!.getTime() - b.due!.getTime())
  return [...dated, ...items.filter(i => !i.due)].map(i => {
    const row: PaneRow = { text: i.text }
    if (i.due) row.left = days(i.due, today)
    return row
  })
}

export function paneProject(name: string, items: Item[], today: Date): PaneProject {
  const groups = GROUPS.map(tag => ({ tag, rows: rowsOf(items.filter(i => i.tag === tag), today) }))
  return { name, ...summarize(items, today), groups: groups.filter(g => g.rows.length > 0) }
}

// 「你要做的」跨專案集中列；等外部只給一行計數加 7 天內到期的；Claude 和未分類收成各專案條數，只展開 7 天內到期的。
const MINE = ['待你決定', '你']
export type ProjectRow = PaneRow & { project: string }
export type MineRow = ProjectRow & { tag: string }
export type CountView = { total: number; counts: { project: string; n: number }[]; soon: ProjectRow[] }

export function splitView(projects: PaneProject[]): { mine: MineRow[]; waiting: CountView; claude: CountView } {
  const far = Number.MAX_SAFE_INTEGER
  const mine: MineRow[] = []
  const waiting: CountView = { total: 0, counts: [], soon: [] }
  const claude: CountView = { total: 0, counts: [], soon: [] }
  for (const p of projects) {
    const n = { waiting: 0, claude: 0 }
    for (const g of p.groups) {
      if (MINE.includes(g.tag)) {
        mine.push(...g.rows.map(r => ({ ...r, tag: g.tag, project: p.name })))
        continue
      }
      const box = g.tag === '等外部' ? waiting : claude
      n[g.tag === '等外部' ? 'waiting' : 'claude'] += g.rows.length
      box.soon.push(...g.rows.filter(r => r.left !== undefined && r.left <= SOON_DAYS).map(r => ({ ...r, project: p.name })))
    }
    if (n.waiting) waiting.counts.push({ project: p.name, n: n.waiting })
    if (n.claude) claude.counts.push({ project: p.name, n: n.claude })
    waiting.total += n.waiting
    claude.total += n.claude
  }
  // 照組別，組內有期限的近的在前，其餘照原順序（sort 是穩定的）
  mine.sort((a, b) => MINE.indexOf(a.tag) - MINE.indexOf(b.tag) || (a.left ?? far) - (b.left ?? far))
  waiting.soon.sort((a, b) => a.left! - b.left!)
  claude.soon.sort((a, b) => a.left! - b.left!)
  return { mine, waiting, claude }
}

// 時間版面：有期限的跨專案照剩幾天排，分已過期、7 天內、之後；沒期限的只算條數。
export type TimeView = { buckets: { name: string; rows: MineRow[] }[]; undated: { mine: number; claude: number } }
const YOURS = ['待你決定', '你', '等外部']

export function timeView(projects: PaneProject[], goals: GoalPlan[] = []): TimeView {
  const dated: MineRow[] = []
  const undated = { mine: 0, claude: 0 }
  for (const p of projects) {
    for (const g of p.groups) {
      for (const r of g.rows) {
        if (r.left !== undefined) dated.push({ ...r, tag: g.tag, project: p.name })
        else if (YOURS.includes(g.tag)) undated.mine++
        else undated.claude++
      }
    }
  }
  // goal 計畫本身和併進去的條目已從各專案拿掉，帶期限的在這裡補回來
  for (const g of goals) {
    if (g.left !== undefined) dated.push({ text: g.title, left: g.left, tag: 'Goal', project: g.project })
    for (const t of g.todos) if (t.left !== undefined) dated.push({ text: t.text, left: t.left, tag: 'Goal', project: t.project })
  }
  dated.sort((a, b) => a.left! - b.left!)
  const buckets = [
    { name: '已過期', rows: dated.filter(r => r.left! < 0) },
    { name: `${SOON_DAYS} 天內`, rows: dated.filter(r => r.left! >= 0 && r.left! <= SOON_DAYS) },
    { name: '之後', rows: dated.filter(r => r.left! > SOON_DAYS) },
  ]
  return { buckets: buckets.filter(b => b.rows.length > 0), undated }
}

export function goalsOf(index: TodoIndex, today: Date): GoalPlan[] {
  return index.goals.map(g => {
    const plan: GoalPlan = { project: g.project, title: g.title, file: g.file, sections: g.sections, from: [], todos: [] }
    const due = dateOf(g.due)
    if (due) plan.left = days(due, today)
    if (g.next) plan.next = g.next
    return plan
  })
}

// 所在專案有設 session_log 就看它的，沒設的看 home 專案的。
export function nextOf(index: TodoIndex, at: string | undefined, home: string | undefined): NextStep | null {
  const own = index.projects.find(p => p.name === at && p.log) ?? index.projects.find(p => p.name === home)
  return own?.next ? { project: own.name, ...own.next } : null
}

// 在 home 專案或不在任何專案底下開 session：列全部專案，所在專案排第一。
// 在其他專案開：只列那個專案自己的，goal 計畫也只列跟它有關的。
export function paneData(index: TodoIndex, today: Date, at: string | undefined, home: string | undefined, now: Date = today): PaneData {
  const goals = goalsOf(index, today)
  const byId = new Map(index.goals.map((g, k) => [g.id, goals[k]!]))
  const rest: [string, Item[]][] = index.projects.map(p => [
    p.name,
    itemsOf(p.items).filter(i => {
      const g = i.goal ? byId.get(i.goal) : undefined
      if (!g) return true
      if (!g.from.includes(p.name)) g.from.push(p.name)
      if (i.merged) {
        const t: GoalTodo = { project: p.name, text: i.text }
        if (i.due) t.left = days(i.due, today)
        g.todos.push(t)
      }
      return false
    }),
  ])
  const only = at && at !== home
  const picked = only
    ? rest.filter(([p]) => p === at)
    : [...rest.filter(([p]) => p === at), ...rest.filter(([p, items]) => p !== at && items.length > 0)]
  return {
    date: stamp(now),
    next: nextOf(index, at, home),
    goals: only ? goals.filter(g => g.project === at || g.from.includes(at)) : goals,
    projects: picked.map(([p, items]) => paneProject(p, items, today)),
  }
}

export function hintData(now: Date, hint = HINT): PaneData {
  return { date: stamp(now), next: null, goals: [], projects: [], hint }
}

export function renderGoals(goals: GoalPlan[]): string {
  if (goals.length === 0) return '沒有進行中的 goal 計畫（未完成 TODO 條目引用、內文寫了 /goal 的計畫檔）。'
  const out = [`進行中的 goal 計畫 ${goals.length} 份`]
  for (const g of goals) {
    const due = g.left === undefined ? '' : g.left < 0 ? `［已過期 ${-g.left} 天］` : `［剩 ${g.left} 天］`
    out.push('', `【${g.project}】${g.title}${due}`, `  ${g.file}`)
    for (const s of g.sections) out.push(`  ${s.done}/${s.total}  ${s.name}`)
    if (g.next) out.push(`  接著做：${g.next}`)
    if (g.todos.length) out.push(`  併入的待辦 ${g.todos.length} 條`, ...g.todos.map(t => `  - ${t.project}｜${t.text}`))
  }
  return out.join('\n')
}

// 專案版面：各專案照 GROUPS 分組，最後一組放已加入 goal 計畫的（計畫本身＋併入的條目）。
// 條目全都併進計畫的專案也列出來。
export function byProject(projects: PaneProject[], goals: GoalPlan[] = []): PaneProject[] {
  const goalRows = (name: string): PaneRow[] => [
    ...goals.filter(g => g.project === name).map(g => ({ text: `計畫：${g.title}`, left: g.left })),
    ...goals.flatMap(g => g.todos.filter(t => t.project === name).map(t => ({ text: t.text, left: t.left }))),
  ]
  const names = [...projects.map(p => p.name)]
  for (const g of goals) for (const n of [g.project, ...g.todos.map(t => t.project)]) if (!names.includes(n)) names.push(n)
  return names.map(name => {
    const p = projects.find(x => x.name === name) ?? { name, total: 0, overdue: 0, soon: 0, groups: [] }
    const rows = goalRows(name)
    return rows.length ? { ...p, groups: [...p.groups, { tag: 'Goal', rows }] } : p
  })
}

// ---- 設定檔與路徑 ----

export const norm = (p: string) => p.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()

// 設定資料夾：CLAUDE_CONFIG_DIR，沒設就是家目錄下的 .claude。
export function configDirOf(env: { configDir?: string; home?: string }): string | undefined {
  if (env.configDir) return env.configDir.replace(/\\/g, '/').replace(/\/+$/, '')
  return env.home ? env.home.replace(/\\/g, '/').replace(/\/+$/, '') + '/.claude' : undefined
}

// 設定檔的 root：展開 ~；在 WSL 裡把 E:/x 換成 <wslPrefix>/e/x（wslPrefix 寫 /mnt 或 /mnt/d 都可以）。
export function resolveRoot(root: string, env: { home?: string; isWsl?: boolean }, wslPrefix = '/mnt'): string {
  let r = root.trim().replace(/\\/g, '/')
  if ((r === '~' || r.startsWith('~/')) && env.home) r = env.home.replace(/\\/g, '/').replace(/\/+$/, '') + r.slice(1)
  const m = /^([A-Za-z]):\/?(.*)$/.exec(r)
  if (env.isWsl && m) {
    const base = wslPrefix.replace(/\/+$/, '').replace(/\/[A-Za-z]$/, '')
    r = `${base}/${m[1]!.toLowerCase()}${m[2] ? '/' + m[2] : ''}`
  }
  return r
}

export function rootsOf(conf: TodoConfig, env: { home?: string; isWsl?: boolean }): [string, string][] {
  return (conf.projects ?? []).map(p => [p.name, resolveRoot(p.root, env, conf.wslPrefix)])
}

// session 開在哪個專案底下（子資料夾也算），大小寫與斜線不拘；多個符合取最深的。
export function projectOf(cwd: string, roots: [string, string][]): string | undefined {
  const c = norm(cwd)
  let best: [string, string] | undefined
  for (const [name, root] of roots) {
    const r = norm(root)
    if (c && (c === r || c.startsWith(r + '/')) && (!best || r.length > norm(best[1]).length)) best = [name, root]
  }
  return best?.[0]
}
