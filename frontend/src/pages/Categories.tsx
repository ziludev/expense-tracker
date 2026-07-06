import { useState, useEffect } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { getCategories, createCategory, updateCategory, deleteCategory, Category } from "@/lib/api"
import { Plus, Pencil, Trash2 } from "lucide-react"

const EMOJI_OPTIONS = ["🍔", "🚗", "🛍️", "🎮", "🏠", "💊", "📚", "💰", "☕", "🎬", "✈️", "👕", "🐱", "🎁", "🏥", "📱"]
const COLOR_OPTIONS = ["#ef4444", "#f59e0b", "#8b5cf6", "#06b6d4", "#10b981", "#ec4899", "#6366f1", "#6b7280", "#f97316", "#14b8a6"]

export default function Categories() {
  const [categories, setCategories] = useState<Category[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Category | null>(null)
  const [name, setName] = useState("")
  const [emoji, setEmoji] = useState("💰")
  const [color, setColor] = useState("#6b7280")
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      setCategories(await getCategories())
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => { fetchData() }, [])

  const openEdit = (cat: Category) => {
    setEditing(cat)
    setName(cat.name)
    setEmoji(cat.emoji)
    setColor(cat.color)
    setDialogOpen(true)
  }

  const openNew = () => {
    setEditing(null)
    setName("")
    setEmoji("💰")
    setColor("#6b7280")
    setDialogOpen(true)
  }

  const handleSave = async () => {
    if (!name.trim()) return
    if (editing) {
      await updateCategory(editing.id, { name, emoji, color })
    } else {
      await createCategory({ name, emoji, color })
    }
    setDialogOpen(false)
    fetchData()
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    await deleteCategory(deleteTarget.id)
    setDeleteTarget(null)
    fetchData()
  }

  return (
    <div className="space-y-4 max-w-lg mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">分类管理</h1>
        <Button size="sm" onClick={openNew}>
          <Plus className="size-4" /> 添加分类
        </Button>
      </div>

      {loading ? (
        <p className="text-center py-8 text-muted-foreground">加载中...</p>
      ) : (
        <div className="space-y-2">
          {categories.map(cat => (
            <Card key={cat.id}>
              <CardContent className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center text-lg"
                    style={{ backgroundColor: cat.color + "20", color: cat.color }}
                  >
                    {cat.emoji}
                  </div>
                  <span className="font-medium">{cat.name}</span>
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={() => openEdit(cat)}>
                    <Pencil className="size-4" />
                  </Button>
                  <Button variant="ghost" size="icon" aria-label="删除" onClick={() => setDeleteTarget(cat)}>
                    <Trash2 className="size-4 text-muted-foreground" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Delete confirmation dialog (deleting cascades to all expenses in it) */}
      <Dialog open={deleteTarget !== null} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除分类</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground">
            删除「{deleteTarget?.emoji} {deleteTarget?.name}」将同时删除该分类下的<span className="text-destructive font-medium">所有支出记录</span>，此操作无法恢复。
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>取消</Button>
            <Button variant="destructive" onClick={handleDelete}>删除</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit/Create dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "编辑分类" : "添加分类"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>名称</Label>
              <Input value={name} onChange={e => setName(e.target.value)} placeholder="分类名称" />
            </div>
            <div className="space-y-2">
              <Label>图标</Label>
              <div className="flex flex-wrap gap-2">
                {EMOJI_OPTIONS.map(e => (
                  <button
                    key={e}
                    className={`w-10 h-10 rounded-lg text-lg flex items-center justify-center border-2 transition-colors ${emoji === e ? "border-primary bg-primary/10" : "border-transparent hover:border-muted-foreground/30"}`}
                    onClick={() => setEmoji(e)}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label>颜色</Label>
              <div className="flex flex-wrap gap-2">
                {COLOR_OPTIONS.map(c => (
                  <button
                    key={c}
                    className={`w-8 h-8 rounded-full border-2 transition-all ${color === c ? "border-primary scale-110" : "border-transparent"}`}
                    style={{ backgroundColor: c }}
                    onClick={() => setColor(c)}
                  />
                ))}
              </div>
            </div>
            <Button className="w-full" onClick={handleSave}>保存</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
