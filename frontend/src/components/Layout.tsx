import { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { clearSession, currentUser } from '../api'

const nav = [
  { to: '/', label: 'Dashboard', icon: '◉' },
  { to: '/network', label: 'Network', icon: '🕸' },
  { to: '/team', label: 'My Team', icon: '🤝' },
  { to: '/payouts', label: 'Payouts', icon: '💸' },
  { to: '/settings', label: 'Webhooks', icon: '⚙' },
]

export default function Layout({ children, title }: { children: ReactNode; title: string }) {
  const user = currentUser()
  const navigate = useNavigate()
  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-edge bg-panel/60 p-5 md:flex">
        <div className="mb-8 font-display text-xl font-bold">
          <span className="text-mint">Adoption</span> HQ
        </div>
        <nav className="flex-1 space-y-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 font-medium transition-colors duration-150 ${
                  isActive ? 'bg-mint/10 text-mint' : 'text-fog hover:text-snow'
                }`
              }
            >
              <span className="w-5 text-center">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
          {user?.role === 'admin' && (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 font-medium transition-colors duration-150 ${
                  isActive ? 'bg-gold/10 text-gold' : 'text-fog hover:text-snow'
                }`
              }
            >
              <span className="w-5 text-center">🛠</span>
              Admin
            </NavLink>
          )}
        </nav>
        <div className="border-t border-edge pt-4">
          <div className="truncate text-sm font-medium">{user?.name}</div>
          <div className="truncate text-xs text-fog">{user?.email}</div>
          <button
            className="mt-3 text-sm text-fog hover:text-coral transition-colors duration-150"
            onClick={() => {
              clearSession()
              navigate('/login')
            }}
          >
            Sign out →
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6 md:p-10">
        <h1 className="mb-8 font-display text-3xl font-bold">{title}</h1>
        {children}
      </main>
    </div>
  )
}
