import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { getCategories, createExpense, ocrReceipt, Category, OCRResult } from "@/lib/api"
import { Upload, Camera, Loader2, CheckCircle } from "lucide-react"

export default function AddExpense({ onSuccess }: { onSuccess: () => void }) {
  const [categories, setCategories] = useState<Category[]>([])
  const [amount, setAmount] = useState("")
  const [categoryId, setCategoryId] = useState("")
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [ocrLoading, setOcrLoading] = useState(false)
  const [ocrResult, setOcrResult] = useState<OCRResult | null>(null)
  const [message, setMessage] = useState("")
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getCategories().then(setCategories).catch(console.error)
  }, [])

  const handleSubmit = async () => {
    if (!amount || !categoryId || !date) {
      setMessage("请填写金额、分类和日期")
      return
    }
    setSubmitting(true)
    try {
      await createExpense({
        amount: parseFloat(amount),
        category_id: parseInt(categoryId),
        date,
        note,
      })
      setAmount("")
      setCategoryId("")
      setNote("")
      setOcrResult(null)
      setMessage("✅ 添加成功！")
      onSuccess()
    } catch (e) {
      setMessage(`❌ 添加失败：${e}`)
    }
    setSubmitting(false)
  }

  const handleOCR = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setOcrLoading(true)
    setOcrResult(null)
    try {
      const result = await ocrReceipt(file)
      setOcrResult(result)

      if (result.success) {
        if (result.suggested_amount) {
          setAmount(String(result.suggested_amount))
        }
        if (result.suggested_date) {
          setDate(result.suggested_date)
        }
      }
    } catch (err) {
      setOcrResult({ success: false, error: String(err) })
    }
    setOcrLoading(false)
  }

  return (
    <div className="space-y-4 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold">记一笔</h1>

      {/* OCR Upload */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Camera className="size-4" /> 拍照识别账单
          </CardTitle>
        </CardHeader>
        <CardContent>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleOCR}
          />
          <Button
            variant="outline"
            className="w-full h-20 border-dashed gap-2"
            onClick={() => fileRef.current?.click()}
            disabled={ocrLoading}
          >
            {ocrLoading ? (
              <><Loader2 className="size-5 animate-spin" /> 识别中...</>
            ) : (
              <><Upload className="size-5" /> 点击上传账单截图</>
            )}
          </Button>

          {ocrResult && (
            <div className="mt-3">
              {ocrResult.success ? (
                <div className="space-y-2">
                  <p className="text-sm text-green-600 flex items-center gap-1">
                    <CheckCircle className="size-4" /> 识别成功
                  </p>
                  <div className="text-xs text-muted-foreground max-h-24 overflow-y-auto border rounded p-2">
                    {ocrResult.lines?.map((l, i) => (
                      <div key={i} className="flex justify-between">
                        <span>{l.text}</span>
                        <span>{(l.confidence * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-red-500">识别失败：{ocrResult.error}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Manual form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">手动录入</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>金额 *</Label>
            <Input
              type="number"
              step="0.01"
              placeholder="0.00"
              value={amount}
              onChange={e => setAmount(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label>分类 *</Label>
            <Select value={categoryId} onValueChange={setCategoryId}>
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
            <Input type="date" value={date} onChange={e => setDate(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>备注</Label>
            <Textarea placeholder="买了什么..." value={note} onChange={e => setNote(e.target.value)} rows={2} />
          </div>

          {message && (
            <p className={`text-sm ${message.startsWith("✅") ? "text-green-600" : "text-destructive"}`}>
              {message}
            </p>
          )}

          <Button className="w-full" onClick={handleSubmit} disabled={submitting}>
            {submitting ? <Loader2 className="size-4 animate-spin" /> : null}
            添加支出
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
