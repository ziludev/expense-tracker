import { useState, useCallback } from "react"
import Layout from "@/components/Layout"
import Dashboard from "@/pages/Dashboard"
import Expenses from "@/pages/Expenses"
import AddExpense from "@/pages/AddExpense"
import Categories from "@/pages/Categories"

type Page = "dashboard" | "expenses" | "add" | "categories"

export default function App() {
  const [page, setPage] = useState<Page>("dashboard")
  const [refreshKey, setRefreshKey] = useState(0)

  const handleSuccess = useCallback(() => {
    setRefreshKey(k => k + 1)
  }, [])

  const renderPage = () => {
    switch (page) {
      case "dashboard":
        return <Dashboard key={`dash-${refreshKey}`} />
      case "expenses":
        return <Expenses key={`exp-${refreshKey}`} />
      case "add":
        return <AddExpense key={`add-${refreshKey}`} onSuccess={() => { handleSuccess(); setPage("expenses") }} />
      case "categories":
        return <Categories key={`cat-${refreshKey}`} />
    }
  }

  return (
    <Layout page={page} setPage={setPage}>
      {renderPage()}
    </Layout>
  )
}
