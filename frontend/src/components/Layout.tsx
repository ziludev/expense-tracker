import { useState, useEffect } from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  LayoutDashboard,
  Receipt,
  PlusCircle,
  Tags,
  Moon,
  Sun,
} from "lucide-react"

type Page = "dashboard" | "expenses" | "add" | "categories"

export default function Layout({ children, page, setPage }: {
  children: React.ReactNode
  page: Page
  setPage: (p: Page) => void
}) {
  const [dark, setDark] = useState(() => {
    if (typeof window === "undefined") return false
    // Persisted choice wins; fall back to the system preference
    const saved = localStorage.getItem("theme")
    if (saved) return saved === "dark"
    return window.matchMedia("(prefers-color-scheme: dark)").matches
  })

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    localStorage.setItem("theme", dark ? "dark" : "light")
  }, [dark])

  const navItems: { id: Page; label: string; icon: React.ElementType }[] = [
    { id: "dashboard", label: "概览", icon: LayoutDashboard },
    { id: "expenses", label: "账单", icon: Receipt },
    { id: "add", label: "记一笔", icon: PlusCircle },
    { id: "categories", label: "分类", icon: Tags },
  ]

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="hidden md:flex w-56 flex-col border-r bg-sidebar">
        <div className="flex h-14 items-center gap-2 px-4 border-b">
          <span className="text-lg">💰</span>
          <span className="font-semibold">记账本</span>
        </div>
        <ScrollArea className="flex-1 py-2">
          <nav className="grid gap-1 px-2">
            {navItems.map((item) => (
              <Button
                key={item.id}
                variant={page === item.id ? "secondary" : "ghost"}
                className="justify-start gap-3 h-10"
                onClick={() => setPage(item.id)}
              >
                <item.icon className="size-4" />
                {item.label}
              </Button>
            ))}
          </nav>
        </ScrollArea>
        <Separator />
        <div className="p-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={() => setDark(!dark)}
          >
            {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
            {dark ? "浅色模式" : "深色模式"}
          </Button>
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 border-t bg-background flex items-center justify-around h-14">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setPage(item.id)}
            className={cn(
              "flex flex-col items-center gap-0.5 px-3 py-1 text-xs",
              page === item.id ? "text-primary" : "text-muted-foreground"
            )}
          >
            <item.icon className="size-5" />
            {item.label}
          </button>
        ))}
      </div>

      {/* Main content */}
      <main className="flex-1 overflow-auto pb-14 md:pb-0">
        <div className="max-w-5xl mx-auto p-4 md:p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
