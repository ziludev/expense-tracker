import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
  }).format(amount)
}

// Format a Date as YYYY-MM-DD using the LOCAL timezone.
// toISOString() converts to UTC first, which yields yesterday's date
// before 08:00 in UTC+8 — never use it for calendar dates.
export function toLocalDateString(d: Date = new Date()): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

// Shift a YYYY-MM string by delta months using local calendar math
export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number)
  return toLocalDateString(new Date(y, m - 1 + delta, 1)).slice(0, 7)
}

export function formatDate(dateStr: string): string {
  // Parse the YYYY-MM-DD parts directly: new Date(dateStr) treats the string
  // as UTC midnight, which renders the previous day in UTC-negative zones
  const [, m, d] = dateStr.split("-").map(Number)
  return `${m}月${d}日`
}
