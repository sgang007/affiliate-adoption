import { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { currentUser, getToken } from './api'
import Admin from './pages/Admin'
import Dashboard from './pages/Dashboard'
import Join from './pages/Join'
import Login from './pages/Login'
import Network from './pages/Network'
import Payouts from './pages/Payouts'
import ProductDetail from './pages/ProductDetail'
import Team from './pages/Team'

function Private({ children }: { children: ReactNode }) {
  return getToken() ? <>{children}</> : <Navigate to="/login" replace />
}

function AdminOnly({ children }: { children: ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return currentUser()?.role === 'admin' ? <>{children}</> : <Navigate to="/" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/join/:token" element={<Join />} />
        <Route path="/" element={<Private><Dashboard /></Private>} />
        <Route path="/products/:id" element={<Private><ProductDetail /></Private>} />
        <Route path="/network" element={<Private><Network /></Private>} />
        <Route path="/team" element={<Private><Team /></Private>} />
        <Route path="/payouts" element={<Private><Payouts /></Private>} />
        <Route path="/admin" element={<AdminOnly><Admin /></AdminOnly>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
