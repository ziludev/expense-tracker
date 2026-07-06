# 记账网站 — 实现方案

> **目标：** 一个支持 OCR 识别账单的个人记账网站，能直观展示花销趋势和分类统计。

## 架构

```
~/learn/expense-tracker/
├── backend/           # FastAPI + SQLite + PaddleOCR
│   ├── main.py        # API 入口
│   ├── models.py      # SQLite 表结构
│   ├── ocr.py         # PaddleOCR 封装
│   └── requirements.txt
└── frontend/          # React + Vite + shadcn/ui + Recharts
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   ├── pages/
    │   ├── lib/
    │   └── hooks/
    └── ...
```

**后端：** FastAPI + SQLite。负责数据持久化、OCR 识别。轻量，一个文件启动。
**前端：** React + TypeScript + Vite + shadcn/ui + Tailwind CSS v4 + Recharts（图表）。
**为什么需要后端：** PaddleOCR 是 Python 库，无法在前端运行；SQLite 避免浏览器 IndexedDB 的跨设备/清缓存丢失问题。

## 功能清单

### P0（核心）
1. **支出列表** — 分页、按日期/类别筛选、关键词搜索
2. **添加支出** — 金额、类别、日期、备注，手动录入
3. **Dashboard 图表** — 月度趋势折线图 + 分类占比饼图
4. **分类管理** — 预设分类（餐饮/交通/购物/娱乐/居住/其他），可增加/删除/修改 emoji 图标

### P1（增强）
5. **OCR 识别账单** — 上传截图/拍照 → 后端 PaddleOCR 解析 → 自动填充表单
6. **月度预算** — 设置总预算，Dashboard 显示已花/剩余进度条
7. **导出 CSV** — 一键导出所有数据

### P2（锦上添花）
8. **日历热力图** — 类似 GitHub 贡献图，展示每日花销
9. **暗色模式** — 跟随系统
10. **今日/本周/本月快捷统计卡片**

## 数据模型

```sql
categories: id, name, emoji, color, created_at
expenses:   id, amount, category_id, date, note, receipt_path, created_at
budgets:    id, month(YYYY-MM), amount, created_at
```

## 技术选型

| 层 | 选择 | 原因 |
|---|---|---|
| 前端框架 | React 18 + Vite | 快，生态好 |
| UI 库 | shadcn/ui | 用户偏好，组件质量高 |
| 样式 | Tailwind CSS v4 | 与 shadcn/ui 配套 |
| 图表 | Recharts | React 原生，API 简洁 |
| 后端 | FastAPI | 轻量，Python 生态 |
| 数据库 | SQLite | 零配置，数据文件在 ~/learn/expense-tracker/ |
| OCR | PaddleOCR small | 已测试通过 |

## 页面设计

```
/          — Dashboard（统计卡片 + 趋势图 + 分类饼图 + 预算进度）
/expenses  — 支出列表（表格 + 筛选 + 搜索 + 分页）
/add       — 添加支出（表单 + OCR 上传区）
/categories — 分类管理
```

## UI 风格

- 暗色侧边栏 + 亮色内容区，跟随系统
- 卡片式布局，大数字展示
- shadcn/ui 默认样式，不自定义主题

---

**任务拆解：** 共 12 步，从后端到前端，从前端到集成测试。
