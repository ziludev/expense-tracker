const API_BASE = "/api"

// URL builders for plain <a> links, so pages never hardcode the API prefix
export const exportCsvUrl = `${API_BASE}/export/csv`
export const receiptUrl = (filename: string) => `${API_BASE}/receipts/${encodeURIComponent(filename)}`

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// Categories
export interface Category {
  id: number
  name: string
  emoji: string
  color: string
}

export const getCategories = () => request<Category[]>("/categories")
export const createCategory = (body: { name: string; emoji: string; color: string }) =>
  request<Category>("/categories", { method: "POST", body: JSON.stringify(body) })
export const updateCategory = (id: number, body: { name: string; emoji: string; color: string }) =>
  request<Category>(`/categories/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteCategory = (id: number) =>
  request<{ ok: boolean }>(`/categories/${id}`, { method: "DELETE" })

// Expenses
export interface Expense {
  id: number
  amount: number
  category_id: number
  date: string
  note: string
  receipt_path: string
  category_name: string
  category_emoji: string
  category_color: string
  created_at: string
}

export interface ExpenseListResponse {
  items: Expense[]
  total: number
  page: number
  page_size: number
}

export const getExpenses = (params: {
  page?: number
  page_size?: number
  category_id?: number
  keyword?: string
  date_from?: string
  date_to?: string
}) => {
  const sp = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") sp.set(k, String(v))
  })
  return request<ExpenseListResponse>(`/expenses?${sp}`)
}

// receipt_path: filename under backend uploads/, returned by the OCR API;
// pass it through so the uploaded image gets linked to the expense
export interface ExpensePayload {
  amount: number
  category_id: number
  date: string
  note: string
  receipt_path?: string
}

export const createExpense = (body: ExpensePayload) =>
  request<Expense>("/expenses", { method: "POST", body: JSON.stringify(body) })

export const updateExpense = (id: number, body: ExpensePayload) =>
  request<Expense>(`/expenses/${id}`, { method: "PUT", body: JSON.stringify(body) })

export const deleteExpense = (id: number) =>
  request<{ ok: boolean }>(`/expenses/${id}`, { method: "DELETE" })

// OCR
export interface OCRResult {
  success: boolean
  lines?: { text: string; confidence: number }[]
  suggested_amount?: number | null
  suggested_date?: string | null
  receipt_path?: string
  error?: string
}

export const ocrReceipt = async (file: File): Promise<OCRResult> => {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${API_BASE}/ocr`, { method: "POST", body: form })
  if (!res.ok) {
    // 413/415/500 return {detail}, not an OCRResult — normalize the shape
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    return { success: false, error: err.detail || `HTTP ${res.status}` }
  }
  return res.json()
}

// Stats
export interface Summary {
  month: string
  total: number
  daily_avg: number
  budget: number
  budget_remaining: number
  budget_percent: number
}

export interface TrendPoint {
  date: string
  amount: number
}

export interface CategoryStat {
  id: number
  name: string
  emoji: string
  color: string
  total: number
}

export interface HeatmapPoint {
  date: string
  amount: number
}

export const getSummary = (month?: string) => {
  const sp = month ? `?month=${month}` : ""
  return request<Summary>(`/stats/summary${sp}`)
}
export const getTrend = (month?: string) => {
  const sp = month ? `?month=${month}` : ""
  return request<TrendPoint[]>(`/stats/trend${sp}`)
}
export const getByCategory = (month?: string) => {
  const sp = month ? `?month=${month}` : ""
  return request<CategoryStat[]>(`/stats/by_category${sp}`)
}
export const getHeatmap = () => request<HeatmapPoint[]>("/stats/heatmap")

// Budgets
export interface Budget {
  id: number
  month: string
  amount: number
}

export const getBudgets = () => request<Budget[]>("/budgets")
export const setBudget = (body: { month: string; amount: number }) =>
  request<Budget>("/budgets", { method: "POST", body: JSON.stringify(body) })
