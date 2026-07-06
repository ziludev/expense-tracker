import { useState } from "react"
import Layout from "@/components/Layout"
import Dashboard from "@/pages/Dashboard"
import Expenses from "@/pages/Expenses"
import AddExpense from "@/pages/AddExpense"
import Categories from "@/pages/Categories"

type Page = "dashboard" | "expenses" | "add" | "categories"

// Only one page is rendered at a time, so every page remounts (and refetches)
// on navigation — no global refresh key is needed.
export default function App() {
  const [page, setPage] = useState<Page>("dashboard")

  const renderPage = () => {
    switch (page) {
      case "dashboard":
        return <Dashboard />
      case "expenses":
        return <Expenses />
      case "add":
        return <AddExpense />
      case "categories":
        return <Categories />
    }
  }

  return (
    <Layout page={page} setPage={setPage}>
      {renderPage()}
    </Layout>
  )
}
