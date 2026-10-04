import { FormEvent, useEffect, useState } from 'react'
import { api, inr } from '../api'
import Layout from '../components/Layout'
import { Chip, CopyField, Empty, ErrorNote, Stat } from '../components/ui'

type Tab = 'products' | 'users' | 'payouts'

export default function Admin() {
  const [tab, setTab] = useState<Tab>('products')
  const [overview, setOverview] = useState<any>(null)

  useEffect(() => {
    api.get('/api/admin/overview').then(setOverview)
  }, [tab])

  return (
    <Layout title="Admin Console">
      {overview && (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Products" value={String(overview.products)} />
          <Stat label="Affiliates" value={String(overview.affiliates)} accent="mint" />
          <Stat label="Commissions owed" value={inr(overview.total_commissions)} accent="gold" />
          <Stat label="Bills awaiting payout" value={String(overview.pending_invoices)} />
        </div>
      )}
      <div className="mb-6 flex gap-2">
        {(['products', 'users', 'payouts'] as Tab[]).map((t) => (
          <button
            key={t}
            className={`btn px-4 py-2 text-sm ${tab === t ? 'bg-mint/10 text-mint border border-mint/40' : 'border border-edge text-fog hover:text-snow'}`}
            onClick={() => setTab(t)}
          >
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === 'products' && <ProductsTab />}
      {tab === 'users' && <UsersTab />}
      {tab === 'payouts' && <PayoutsTab />}
    </Layout>
  )
}

function ProductsTab() {
  const [products, setProducts] = useState<any[]>([])
  const [form, setForm] = useState({
    name: '', description: '', url: '', price: 1800,
    signup_commission: 100, trial_commission: 300, subscription_pct: 20,
  })
  const [error, setError] = useState('')

  function load() {
    api.get('/api/admin/products').then(setProducts)
  }
  useEffect(load, [])

  async function create(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/api/admin/products', form)
      setForm({ ...form, name: '', description: '', url: '' })
      load()
    } catch (err: any) {
      setError(err.message)
    }
  }

  function set(k: string, v: string | number) {
    setForm({ ...form, [k]: v })
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        {products.length === 0 && <div className="card"><Empty>No products yet — create the first campaign.</Empty></div>}
        {products.map((p) => (
          <div key={p.id} className="card p-6 rise">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="font-display text-lg font-semibold">{p.name}</h3>
              <span className="text-sm text-fog">
                signup {inr(p.signup_commission)} · trial {inr(p.trial_commission)} · subs {p.subscription_pct}% of {inr(p.price)}/mo
              </span>
            </div>
            <p className="mt-1 text-sm text-fog">{p.description}</p>
            <div className="mt-4 space-y-3">
              <CopyField label="Meridian webhook URL (configure in product intelligence engine)" value={p.webhook_url} />
              <CopyField label="Webhook signing secret" value={p.webhook_secret} />
            </div>
          </div>
        ))}
      </div>
      <div className="card h-fit p-6 rise">
        <h2 className="mb-5 font-display text-lg font-semibold">New product</h2>
        <form onSubmit={create} className="space-y-3">
          <input className="input" placeholder="Product name" value={form.name} onChange={(e) => set('name', e.target.value)} required />
          <input className="input" placeholder="Product URL (https://…)" type="url" value={form.url} onChange={(e) => set('url', e.target.value)} required />
          <textarea className="input" rows={3} placeholder="Description" value={form.description} onChange={(e) => set('description', e.target.value)} />
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Price / mo (₹)</label>
              <input className="input" type="number" value={form.price} onChange={(e) => set('price', +e.target.value)} /></div>
            <div><label className="label">Subs %</label>
              <input className="input" type="number" value={form.subscription_pct} onChange={(e) => set('subscription_pct', +e.target.value)} /></div>
            <div><label className="label">Per signup (₹)</label>
              <input className="input" type="number" value={form.signup_commission} onChange={(e) => set('signup_commission', +e.target.value)} /></div>
            <div><label className="label">Per trial (₹)</label>
              <input className="input" type="number" value={form.trial_commission} onChange={(e) => set('trial_commission', +e.target.value)} /></div>
          </div>
          {error && <ErrorNote message={error} />}
          <button className="btn-primary w-full">Create product</button>
        </form>
      </div>
    </div>
  )
}

function UsersTab() {
  const [users, setUsers] = useState<any[]>([])
  const [products, setProducts] = useState<any[]>([])
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [assign, setAssign] = useState({ user_id: 0, product_id: 0 })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  function load() {
    api.get('/api/admin/users').then(setUsers)
    api.get('/api/admin/products').then(setProducts)
  }
  useEffect(load, [])

  async function create(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/api/admin/users', form)
      setForm({ name: '', email: '', password: '' })
      setNotice('Affiliate created — share their login credentials with them.')
      load()
    } catch (err: any) {
      setError(err.message)
    }
  }

  async function doAssign(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      await api.post(`/api/admin/products/${assign.product_id}/assign`, { user_id: assign.user_id })
      setNotice('Product assigned.')
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="card p-6 lg:col-span-2 rise">
        <h2 className="mb-5 font-display text-lg font-semibold">All users</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                <th className="pb-3 pr-4">User</th>
                <th className="pb-3 pr-4">Role</th>
                <th className="pb-3 pr-4">Network level</th>
                <th className="pb-3 text-right">Total earned</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-edge/50">
                  <td className="py-3 pr-4">
                    <div className="font-medium">{u.name}</div>
                    <div className="text-xs text-fog">{u.email}</div>
                  </td>
                  <td className="py-3 pr-4"><Chip status={u.role === 'admin' ? 'paid' : 'signed_up'} /></td>
                  <td className="py-3 pr-4 text-fog">{u.role === 'admin' ? '—' : `L${u.depth}`}</td>
                  <td className="py-3 text-right font-display font-semibold text-gold">{inr(u.total_earned)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="space-y-6">
        <div className="card p-6 rise">
          <h2 className="mb-1 font-display text-lg font-semibold">Create root affiliate</h2>
          <p className="mb-4 text-xs text-fog">The first node of a new network. They invite everyone else themselves.</p>
          <form onSubmit={create} className="space-y-3">
            <input className="input" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <input className="input" type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            <input className="input" type="password" placeholder="Temporary password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
            <button className="btn-primary w-full">Create affiliate</button>
          </form>
        </div>
        <div className="card p-6 rise">
          <h2 className="mb-4 font-display text-lg font-semibold">Assign product</h2>
          <form onSubmit={doAssign} className="space-y-3">
            <select className="input" value={assign.user_id} onChange={(e) => setAssign({ ...assign, user_id: +e.target.value })} required>
              <option value={0} disabled>Select affiliate…</option>
              {users.filter((u) => u.role === 'affiliate').map((u) => (
                <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
              ))}
            </select>
            <select className="input" value={assign.product_id} onChange={(e) => setAssign({ ...assign, product_id: +e.target.value })} required>
              <option value={0} disabled>Select product…</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <button className="btn-primary w-full" disabled={!assign.user_id || !assign.product_id}>Assign</button>
          </form>
        </div>
        {(error || notice) && (
          <div>{error ? <ErrorNote message={error} /> : <div className="rounded-xl border border-leaf/40 bg-leaf/10 px-4 py-2.5 text-sm text-leaf">{notice}</div>}</div>
        )}
      </div>
    </div>
  )
}

function PayoutsTab() {
  const [invoices, setInvoices] = useState<any[]>([])
  const [result, setResult] = useState<any>(null)

  function load() {
    api.get('/api/admin/invoices').then(setInvoices)
  }
  useEffect(load, [])

  async function closeCycle() {
    const res = await api.post('/api/admin/payouts/close-cycle')
    setResult(res)
    load()
  }

  return (
    <div className="space-y-6">
      <div className="card flex flex-wrap items-center justify-between gap-4 p-6 rise">
        <div>
          <h2 className="font-display text-lg font-semibold">Monthly payout cycle</h2>
          <p className="text-sm text-fog">Marks every submitted bill as paid, in one shot.</p>
        </div>
        <button className="btn-primary" onClick={closeCycle}>Run payout cycle 💸</button>
        {result && (
          <div className="w-full text-sm text-leaf">
            Paid {result.invoices_paid} bill{result.invoices_paid === 1 ? '' : 's'} totalling {inr(result.total_paid)}.
          </div>
        )}
      </div>
      <div className="card p-6 rise">
        <h2 className="mb-5 font-display text-lg font-semibold">All bills</h2>
        {invoices.length === 0 ? (
          <Empty>No bills generated yet.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                  <th className="pb-3 pr-4">Bill</th>
                  <th className="pb-3 pr-4">Affiliate</th>
                  <th className="pb-3 pr-4">Payout to</th>
                  <th className="pb-3 pr-4 text-right">Amount</th>
                  <th className="pb-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((i) => (
                  <tr key={i.id} className="border-b border-edge/50">
                    <td className="py-3 pr-4 font-mono text-xs">{i.number}</td>
                    <td className="py-3 pr-4">
                      <div className="font-medium">{i.user.name}</div>
                      <div className="text-xs text-fog">{i.user.email}</div>
                    </td>
                    <td className="py-3 pr-4 font-mono text-xs text-fog">
                      {i.user.payout_details?.upi || i.user.payout_details?.bank_account || 'not set'}
                    </td>
                    <td className="py-3 pr-4 text-right font-display font-semibold text-gold">{inr(i.total_amount)}</td>
                    <td className="py-3"><Chip status={i.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
