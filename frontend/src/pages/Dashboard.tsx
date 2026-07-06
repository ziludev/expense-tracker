import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { formatCurrency, toLocalDateString, shiftMonth } from "@/lib/utils"
import { getSummary, getTrend, getByCategory, getBudgets, setBudget, Summary, TrendPoint, CategoryStat, Budget } from "@/lib/api"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { TrendingUp, Wallet, Calendar, Target } from "lucide-react"

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [trend, setTrend] = useState<TrendPoint[]>([])
  const [categories, setCategories] = useState<CategoryStat[]>([])
  const [budgets, setBudgets] = useState<Budget[]>([])
  const [budgetDialogOpen, setBudgetDialogOpen] = useState(false)
  const [budgetAmount, setBudgetAmount] = useState("")
  const [loading, setLoading] = useState(true)

  const currentMonth = toLocalDateString().slice(0, 7)
  const [month, setMonth] = useState(currentMonth)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [s, t, c, b] = await Promise.all([
        getSummary(month),
        getTrend(month),
        getByCategory(month),
        getBudgets(),
      ])
      setSummary(s)
      setTrend(t)
      setCategories(c)
      setBudgets(b)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => { fetchData() }, [month])

  const handleSetBudget = async () => {
    const amount = parseFloat(budgetAmount)
    if (isNaN(amount) || amount <= 0) return
    await setBudget({ month, amount })
    setBudgetDialogOpen(false)
    setBudgetAmount("")
    fetchData()
  }

  const currentBudget = budgets.find(b => b.month === month)
  const totalColor = summary && summary.budget > 0 && summary.total > summary.budget
    ? "text-red-500" : "text-primary"

  if (loading && !summary) {
    return <div className="flex items-center justify-center h-64 text-muted-foreground">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">概览</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setMonth(m => shiftMonth(m, -1))}>上个月</Button>
          <span className="font-medium min-w-[100px] text-center">{month}</span>
          <Button variant="outline" size="sm" onClick={() => {
            const next = shiftMonth(month, 1)
            if (next <= currentMonth) setMonth(next)
          }} disabled={month >= currentMonth}>下个月</Button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">本月支出</CardTitle>
            <Wallet className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${totalColor}`}>
              {summary ? formatCurrency(summary.total) : "-"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">日均</CardTitle>
            <Calendar className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary ? formatCurrency(summary.daily_avg) : "-"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">预算</CardTitle>
            <Target className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {currentBudget ? formatCurrency(currentBudget.amount) : "-"}
            </div>
            <Dialog open={budgetDialogOpen} onOpenChange={(open) => {
              setBudgetDialogOpen(open)
              // Prefill with the current budget so "修改" starts from the existing value
              if (open) setBudgetAmount(currentBudget ? String(currentBudget.amount) : "")
            }}>
              <DialogTrigger asChild>
                <Button variant="link" size="sm" className="h-auto p-0 text-xs">
                  {currentBudget ? "修改" : "设置预算"}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>设置 {month} 预算</DialogTitle>
                </DialogHeader>
                <Input
                  type="number"
                  placeholder="预算金额"
                  value={budgetAmount}
                  onChange={e => setBudgetAmount(e.target.value)}
                />
                <Button onClick={handleSetBudget}>保存</Button>
              </DialogContent>
            </Dialog>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">剩余</CardTitle>
            <TrendingUp className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${summary && summary.budget_remaining < 0 ? "text-red-500" : "text-green-500"}`}>
              {summary && summary.budget > 0 ? formatCurrency(summary.budget_remaining) : "-"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Budget progress */}
      {currentBudget && summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">预算使用进度</CardTitle>
          </CardHeader>
          <CardContent>
            <Progress value={Math.min(summary.budget_percent, 100)} className="h-3" />
            <p className="text-sm text-muted-foreground mt-2">
              已用 {formatCurrency(summary.total)} / {formatCurrency(currentBudget.amount)}（{summary.budget_percent}%）
            </p>
          </CardContent>
        </Card>
      )}

      {/* Charts */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Line chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">每日趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="date" tickFormatter={(v: string) => v.slice(-2)} fontSize={12} />
                <YAxis fontSize={12} tickFormatter={(v: number) => `¥${v}`} />
                <Tooltip formatter={(v) => [formatCurrency(Number(v ?? 0)), "支出"]} />
                <Line type="monotone" dataKey="amount" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Pie chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">分类占比</CardTitle>
          </CardHeader>
          <CardContent>
            {categories.filter(c => c.total > 0).length === 0 ? (
              <p className="text-muted-foreground text-center py-16">暂无数据</p>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={categories.filter(c => c.total > 0)}
                    dataKey="total"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                  >
                    {categories.filter(c => c.total > 0).map((c) => (
                      <Cell key={c.id} fill={c.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => formatCurrency(Number(v ?? 0))} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
