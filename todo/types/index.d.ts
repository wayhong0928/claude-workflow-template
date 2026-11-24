// ---- todo_index.json：scripts/todo_core.py 寫的快照，mod 只讀 ----
// 日期一律 YYYY-MM-DD；剩幾天由 mod 用當天日期重算。
export type IndexItem = {
  who: '你決定' | '你' | 'Claude' | '等外部' | '未分類' | string
  text: string
  due: string | null
  born: string | null
  touched: string | null
  stale: boolean
  merged: boolean
  goal: string | null
  file: string
  line: number
}
export type IndexProject = {
  name: string
  root: string
  todo: string[]
  log: string | null
  items: IndexItem[]
  next: { title: string; steps: string[] } | null
  // 只有 github.enabled 且該專案設了 github 才有，值是 owner/repo
  github?: string
}
// gh_cache.json 的一筆 issue／PR；repo 只有跨 repo 搜尋（我的）才有
export type IndexGhRow = { number: number; title: string; url: string; updated: string; repo?: string }
export type IndexGithub = {
  enabled: true
  // 最後一次連網的時間（本機時間）；還沒抓過是 null
  fetched: string | null
  // 最近一次抓取的第一個錯誤；沒錯是 null
  error: string | null
  mine: { assigned: IndexGhRow[]; prs: IndexGhRow[]; review: IndexGhRow[] }
  repos: Record<string, { issues: IndexGhRow[]; prs: IndexGhRow[]; error: string | null }>
}
export type IndexGoal = {
  id: string
  project: string
  file: string
  path: string
  title: string
  due: string | null
  sections: GoalSection[]
  next: string | null
}
export type TodoIndex = {
  version: number
  generated: string
  today: string
  config: string | null
  home: string | null
  dueSoonDays: number
  projects: IndexProject[]
  // 只有 github.enabled 才有這個鍵
  github?: IndexGithub
  goals: IndexGoal[]
  expiring: { project: string; path: string; rel: string; due: string; left: number; after: string | null }[]
  problems: { file: string; line: number; kind: string; msg: string }[]
}
// todo.config.json 裡 mod 用得到的欄位：找專案根目錄、判斷 session 在哪個專案。
export type TodoConfig = {
  home?: string
  wslPrefix?: string
  projects?: { name: string; root: string; github?: string }[]
  github?: { enabled?: boolean; ttlMinutes?: number }
  // 側欄要顯示哪些版面、照什麼順序；不設就是四種全開
  views?: string[]
}

// ---- 側欄畫面用的快照 ----
// left 只有帶期限的條目才有：負數是已過期幾天。
export type PaneRow = { text: string; left?: number }
export type PaneProject = {
  name: string
  total: number
  overdue: number
  soon: number
  groups: { tag: string; rows: PaneRow[] }[]
}
// 所在專案 session_log 最新一筆的下一步；沒設 session_log 的專案看 home 專案的。
export type NextStep = { project: string; title: string; steps: string[] }
export type GoalStep = { text: string; isDone: boolean }
export type GoalSection = { name: string; done: number; total: number; steps?: GoalStep[] }
// 側欄版面：mine 你要做的為主、project 照專案全展開、time 照期限、goal 計畫逐步。
export type PaneView = 'mine' | 'project' | 'time' | 'goal'
export type GoalTodo = { project: string; text: string; left?: number }
// todos：寫了「併入 <計畫>」的條目，從各專案清單移到這裡；from：有條目指向這份計畫的專案。
export type GoalPlan = {
  project: string
  title: string
  file: string
  left?: number
  sections: GoalSection[]
  next?: string
  from: string[]
  todos: GoalTodo[]
}
// GitHub 區塊：只有 index 有 github 才有。note 是側欄上那一行淡色說明（更新時間或錯誤）。
export type GhRow = { text: string; url: string }
export type PaneGithub = {
  note: string
  mine: { label: string; rows: GhRow[] }[]
  projects: { name: string; repo: string; issues: GhRow[]; prs: GhRow[]; error?: string }[]
}
// hint：沒有設定檔或 index 時，側欄只顯示這一行。
export type PaneData = {
  date: string
  next: NextStep | null
  goals: GoalPlan[]
  projects: PaneProject[]
  hint?: string
  github?: PaneGithub
  // 側欄顯示的版面（照順序，按鍵 1、2…）；沒有就是四種全開
  views?: PaneView[]
}

declare module 'claude-code' {
  interface PluginState {
    todo: { pane: PaneData | null; isBandHidden: boolean; view: PaneView }
  }
}
