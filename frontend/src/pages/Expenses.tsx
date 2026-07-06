import { useState, useEffect, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { formatCurrency, formatDate } from "@/lib/utils"
import { getExpenses, deleteExpense, updateExpense, getCategories, exportCsvUrl, receiptUrl, Category, Expense } from "@/lib/api"
import { Trash2, Search, ChevronLeft, ChevronRight, Pencil, Download, Paperclip } from "lucide-react"

export default function Expenses() {
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [categories, setCategories] = useState<Category[]>([])
  const [filterCategory, setFilterCategory] = useState("all")
  const [keywordInput, setKeywordInput] = useState("")
  const [keyword, setKeyword] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [loading, setLoading] = useState(true)
  const [deleteId, setDeleteId] = useState<number | null>(null)

  // Edit dialog state
  const [editing, setEditing] = useState<Expense | null>(null)
  const [editAmount, setEditAmount] = useState("")
  const [editCategoryId, setEditCategoryId] = useState("")
  const [editDate, setEditDate] = useState("")
  const [editNote, setEditNote] = useState("")
  const [editError, setEditError] = useState("")

  // Debounce keyword so we don't hit the API on every keystroke
  useEffect(() => {
    const t = setTimeout(() => {
      setKeyword(keywordInput)
      setPage(1)
    }, 300)
    return () => clearTimeout(t)
  }, [keywordInput])

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [cats, data] = await Promise.all([
        getCategories(),
        getExpenses({
          page,
          page_size: 20,
          category_id: filterCategory !== "all" ? parseInt(filterCategory) : undefined,
          keyword: keyword || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
        }),
      ])
      setCategories(cats)
      setExpenses(data.items)
      setTotal(data.total)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }, [page, filterCategory, keyword, dateFrom, dateTo])

  useEffect(() => { fetchData() }, [fetchData])

  const handleDelete = async () => {
    if (deleteId === null) return
    await deleteExpense(deleteId)
    setDeleteId(null)
    fetchData()
  }

  const openEdit = (e: Expense) => {
    setEditing(e)
    setEditAmount(String(e.amount))
    setEditCategoryId(String(e.category_id))
    setEditDate(e.date)
    setEditNote(e.note)
    setEditError("")
  }

  const handleEditSave = async () => {
    if (!editing) return
    const amount = parseFloat(editAmount)
    if (isNaN(amount) || amount <= 0 || !editDate || !editCategoryId) {
      setEditError("请填写有效的金额、分类和日期")
      return
    }
    try {
      await updateExpense(editing.id, {
        amount,
        category_id: parseInt(editCategoryId),
        date: editDate,
        note: editNote,
        // Keep the attached receipt: the update endpoint overwrites all fields
        receipt_path: editing.receipt_path,
      })
      setEditing(null)
      fetchData()
    } catch (err) {
      setEditError(`保存失败：${err}`)
    }
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">账单</h1>
        <Button variant="outline" size="sm" asChild>
          <a href={exportCsvUrl} download>
            <Download className="size-4" /> 导出 CSV
          </a>
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-3">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
                <Input
                  placeholder="搜索备注..."
                  className="pl-8"
                  value={keywordInput}
                  onChange={e => setKeywordInput(e.target.value)}
                />
              </div>
            </div>
            <Select value={filterCategory} onValueChange={v => { setFilterCategory(v); setPage(1) }}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="全部分类" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部分类</SelectItem>
                {categories.map(c => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.emoji} {c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="date"
              className="w-[150px]"
              value={dateFrom}
              onChange={e => { setDateFrom(e.target.value); setPage(1) }}
            />
            <Input
              type="date"
              className="w-[150px]"
              value={dateTo}
              onChange={e => { setDateTo(e.target.value); setPage(1) }}
            />
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-muted-foreground">
            共 {total} 条记录
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-center py-8 text-muted-foreground">加载中...</p>
          ) : expenses.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">暂无记录</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>日期</TableHead>
                    <TableHead>分类</TableHead>
                    <TableHead className="text-right">金额</TableHead>
                    <TableHead>备注</TableHead>
                    <TableHead className="w-28"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {expenses.map(e => (
                    <TableRow key={e.id}>
                      <TableCell className="text-muted-foreground">{formatDate(e.date)}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="gap-1">
                          <span>{e.category_emoji}</span>
                          {e.category_name}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-medium">{formatCurrency(e.amount)}</TableCell>
                      <TableCell className="text-muted-foreground max-w-[200px] truncate">{e.note || "-"}</TableCell>
                      <TableCell className="text-right">
                        {e.receipt_path && (
                          <Button variant="ghost" size="icon" asChild>
                            <a
                              href={receiptUrl(e.receipt_path)}
                              target="_blank"
                              rel="noreferrer"
                              aria-label="查看账单图片"
                            >
                              <Paperclip className="size-4 text-muted-foreground" />
                            </a>
                          </Button>
                        )}
                        <Button variant="ghost" size="icon" aria-label="编辑" onClick={() => openEdit(e)}>
                          <Pencil className="size-4 text-muted-foreground" />
                        </Button>
                        <Button variant="ghost" size="icon" aria-label="删除" onClick={() => setDeleteId(e.id)}>
                          <Trash2 className="size-4 text-muted-foreground" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(p => p - 1)}
                  >
                    <ChevronLeft className="size-4" /> 上一页
                  </Button>
                  <span className="text-sm text-muted-foreground">{page} / {totalPages}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage(p => p + 1)}
                  >
                    下一页 <ChevronRight className="size-4" />
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Edit dialog */}
      <Dialog open={editing !== null} onOpenChange={(open) => { if (!open) setEditing(null) }}>
        <DialogContent>
          <DialogHeader><DialogTitle>编辑支出</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>金额 *</Label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={editAmount}
                onChange={e => setEditAmount(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>分类 *</Label>
              <Select value={editCategoryId} onValueChange={setEditCategoryId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择分类" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map(c => (
                    <SelectItem key={c.id} value={String(c.id)}>{c.emoji} {c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>日期 *</Label>
              <Input type="date" value={editDate} onChange={e => setEditDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>备注</Label>
              <Input value={editNote} onChange={e => setEditNote(e.target.value)} placeholder="买了什么..." />
            </div>
            {editError && <p className="text-sm text-destructive">{editError}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEditing(null)}>取消</Button>
              <Button onClick={handleEditSave}>保存</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete dialog */}
      <Dialog open={deleteId !== null} onOpenChange={() => setDeleteId(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>确认删除</DialogTitle></DialogHeader>
          <p className="text-muted-foreground">删除后无法恢复，确定要删除这条记录吗？</p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteId(null)}>取消</Button>
            <Button variant="destructive" onClick={handleDelete}>删除</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
