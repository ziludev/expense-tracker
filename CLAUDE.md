# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

个人记账网站，支持 OCR 识别账单。前后端分离：`backend/`（FastAPI + SQLite + PaddleOCR）+ `frontend/`（React 19 + Vite + shadcn/ui + Tailwind CSS v4 + Recharts）。整体方案见 `PLAN.md`。

## 常用命令

```bash
# 后端（端口 8765）
cd backend && python main.py            # 依赖: pip install -r requirements.txt
cd backend && ./venv/bin/pytest tests/  # 后端 API 测试（EXPENSE_DB 指向临时库）

# 前端（Vite dev server，/api 代理到 localhost:8765）
cd frontend && npm run dev
cd frontend && npm run build            # tsc -b && vite build
cd frontend && npm run lint             # oxlint
```

前端没有测试套件。本地开发需同时启动前后端，前端通过 Vite proxy 访问后端 API。

## 架构

### 后端 — 单文件 `backend/main.py`

- 全部 API、数据模型、SQLite 建表逻辑都在 `main.py` 一个文件里（PLAN.md 里的 models.py/ocr.py 拆分未实施）。
- SQLite 数据库文件 `backend/expenses.db`，启动时 `init_db()` 自动建表并插入 8 个默认分类。三张表：`categories`、`expenses`、`budgets`（month 唯一，YYYY-MM）。
- 每个请求单独 `get_db()` 开连接、用完即关，WAL 模式。日期以 TEXT 存储（YYYY-MM-DD），月度统计用 `date LIKE 'YYYY-MM%'` 匹配。
- PaddleOCR 在 `/api/ocr` 内部懒加载 import（首次调用慢），上传图片存 `backend/uploads/`，并用正则从识别文本中提取金额（¥/合计）和日期作为建议值。OCR 失败返回 `{"success": false}` 而不是抛错。

### 前端 — 无路由库的状态切换

- `src/App.tsx` 用 `useState<Page>` 切换 4 个页面（dashboard/expenses/add/categories），**没有 react-router**；同一时间只渲染一个页面，切页即重挂载并重新拉取数据。
- `src/lib/api.ts` 是唯一的 API 层：所有后端接口的 typed fetch 封装 + TypeScript 接口定义。新增后端接口时在这里加对应函数和类型。
- `src/components/ui/` 是 shadcn/ui 生成的组件（Radix 底层），不要手改样式逻辑；页面组件在 `src/pages/`。
- 路径别名 `@` → `frontend/src`（vite.config.ts + tsconfig）。
