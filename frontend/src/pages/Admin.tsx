import { FormEvent, useEffect, useState } from 'react'
import { api, inr } from '../api'
import Layout from '../components/Layout'
import { Chip, CopyField, Empty, ErrorNote, Stat } from '../components/ui'

type Tab = 'products' | 'users' | 'payouts'
const EVENTS = ['visited', 'signed_up', 'trial', 'subscribed']

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
          <Stat label="Payout requests open" value={String(overview.pending_payout_requests)} />
        </div>
      )}
      <div className="mb-6 flex gap-2">
        {(['products', 'users', 'payouts'] as Tab[]).map((t) => (
          <button
            key={t}
            className={`btn px-4 py-2 text-sm ${tab === t ? 'bg-mint/10 text-mint border border-mint/40' : 'border border-edge text-fog hover:text-snow'}`}
            onClick={() => setTab(t)}
          >
            {t === 'payouts' ? 'Payout requests' : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === 'products' && <ProductsTab />}
      {tab === 'users' && <UsersTab />}
      {tab === 'payouts' && <PayoutsTab />}
    </Layout>
  )
}

/* ---------------- Products: the full setup workflow ---------------- */

function ProductsTab() {
  const [products, setProducts] = useState<any[]>([])
  const [form, setForm] = useState({ name: '', description: '', url: '', price: 2000, network_commission_pct: 20 })
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

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-5 lg:col-span-2">
        {products.length === 0 && (
          <div className="card"><Empty>No products yet — create your first campaign on the right.</Empty></div>
        )}
        {products.map((p) => (
          <ProductEditor key={p.id} product={p} onChange={load} />
        ))}
      </div>
      <div className="card h-fit p-6 shadow-glow rise">
        <h2 className="mb-1 font-display text-lg font-semibold">1 · Create product</h2>
        <p className="mb-4 text-xs text-fog">
          You become the network root (admins earn nothing). Then: 2 · tune the incentive rules,
          3 · copy the integration prompt into the product's codebase, 4 · invite affiliates.
        </p>
        <form onSubmit={create} className="space-y-3">
          <input className="input" placeholder="Product name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <input className="input" placeholder="Product URL (https://getmeridian.tech)" type="url" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} required />
          <textarea className="input" rows={2} placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">List price / mo (₹)</label>
              <input className="input" type="number" value={form.price} onChange={(e) => setForm({ ...form, price: +e.target.value })} />
            </div>
            <div>
              <label className="label">Network commission %</label>
              <input className="input" type="number" min={0} max={90} value={form.network_commission_pct} onChange={(e) => setForm({ ...form, network_commission_pct: +e.target.value })} />
            </div>
          </div>
          {error && <ErrorNote message={error} />}
          <button className="btn-primary w-full">Create product</button>
        </form>
      </div>
    </div>
  )
}

function ProductEditor({ product, onChange }: { product: any; onChange: () => void }) {
  const [open, setOpen] = useState<'rules' | 'templates' | 'integration' | null>(null)
  const [prompt, setPrompt] = useState('')
  const [pct, setPct] = useState(product.network_commission_pct)
  const [error, setError] = useState('')

  async function showPrompt() {
    if (open === 'integration') return setOpen(null)
    const res = await api.get(`/api/admin/products/${product.id}/integration-prompt`)
    setPrompt(res.prompt)
    setOpen('integration')
  }

  async function savePct() {
    setError('')
    try {
      await api.patch(`/api/admin/products/${product.id}`, { network_commission_pct: pct })
      onChange()
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div className="card p-6 rise">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="font-display text-lg font-semibold">{product.name}</h3>
          <a href={product.url} target="_blank" rel="noreferrer" className="font-mono text-xs text-mint">{product.url}</a>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-fog">Network commission</span>
          <input className="input w-20 px-2 py-1 text-center" type="number" min={0} max={90} value={pct} onChange={(e) => setPct(+e.target.value)} />
          <span className="text-fog">%</span>
          {pct !== product.network_commission_pct && (
            <button className="btn-ghost px-3 py-1 text-xs" onClick={savePct}>Save</button>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button className={`btn-ghost px-3 py-1.5 text-xs ${open === 'rules' ? 'border-mint/60 text-mint' : ''}`} onClick={() => setOpen(open === 'rules' ? null : 'rules')}>
          ⚖ Incentive rules
        </button>
        <button className={`btn-ghost px-3 py-1.5 text-xs ${open === 'templates' ? 'border-mint/60 text-mint' : ''}`} onClick={() => setOpen(open === 'templates' ? null : 'templates')}>
          ✉ Event messages
        </button>
        <button className={`btn-ghost px-3 py-1.5 text-xs ${open === 'integration' ? 'border-mint/60 text-mint' : ''}`} onClick={showPrompt}>
          ⚡ Integration prompt
        </button>
      </div>
      {error && <div className="mt-3"><ErrorNote message={error} /></div>}

      {open === 'rules' && <RulesEditor product={product} onChange={onChange} />}
      {open === 'templates' && <TemplatesEditor product={product} onChange={onChange} />}
      {open === 'integration' && (
        <div className="mt-5 space-y-3 border-t border-edge pt-5">
          <p className="text-sm text-fog">
            Paste this into the product's codebase (or hand it to an AI coding agent). It contains the
            channel-caching snippet, the <code className="font-mono text-mint">referrer_id</code> column
            instruction, all message formats and the signing secret.
          </p>
          <div className="flex gap-2">
            <button
              className="btn-primary px-3 py-1.5 text-xs"
              onClick={() => navigator.clipboard.writeText(prompt)}
            >
              Copy full prompt
            </button>
          </div>
          <pre className="max-h-96 overflow-auto rounded-xl bg-ink border border-edge p-4 font-mono text-xs leading-relaxed text-snow/90 whitespace-pre-wrap">{prompt}</pre>
          <div className="space-y-3">
            <CopyField label="Webhook URL" value={product.webhook_url} />
            <CopyField label="Signing secret" value={product.webhook_secret} />
          </div>
        </div>
      )}
    </div>
  )
}

function RulesEditor({ product, onChange }: { product: any; onChange: () => void }) {
  const byEvent: Record<string, any> = {}
  for (const r of product.rules) byEvent[r.event] = r
  const [drafts, setDrafts] = useState<Record<string, any>>(() => {
    const d: Record<string, any> = {}
    for (const ev of EVENTS)
      d[ev] = byEvent[ev] ?? { event: ev, type: 'flat', value: 0, field: '' }
    return d
  })
  const [saved, setSaved] = useState('')
  const [error, setError] = useState('')

  async function save(ev: string) {
    setError('')
    setSaved('')
    const d = drafts[ev]
    try {
      await api.put(`/api/admin/products/${product.id}/rules`, {
        event: ev,
        type: d.type,
        value: +d.value,
        field: d.type === 'commission' ? d.field || 'params.subscription' : null,
      })
      setSaved(ev)
      onChange()
    } catch (e: any) {
      setError(e.message)
    }
  }

  function set(ev: string, patch: any) {
    setDrafts({ ...drafts, [ev]: { ...drafts[ev], ...patch } })
  }

  return (
    <div className="mt-5 space-y-3 border-t border-edge pt-5">
      <p className="text-sm text-fog">
        What the network earns per event. <b className="text-snow">Flat</b> pays a fixed amount;{' '}
        <b className="text-snow">commission</b> pays a % of a field from the event message (e.g.{' '}
        <code className="font-mono text-mint">params.subscription</code>). Subscribed pays once per
        user per month — recurring while the product keeps sending it.
      </p>
      {error && <ErrorNote message={error} />}
      {EVENTS.map((ev) => {
        const d = drafts[ev]
        return (
          <div key={ev} className="flex flex-wrap items-center gap-3 rounded-xl border border-edge p-3">
            <div className="w-28"><Chip status={ev} /></div>
            <select className="input w-36 py-1.5" value={d.type} onChange={(e) => set(ev, { type: e.target.value })}>
              <option value="flat">Flat ₹</option>
              <option value="commission">Commission %</option>
            </select>
            <input
              className="input w-28 py-1.5 text-right"
              type="number"
              step="0.01"
              value={d.value}
              onChange={(e) => set(ev, { value: e.target.value })}
            />
            {d.type === 'commission' && (
              <input
                className="input flex-1 min-w-40 py-1.5 font-mono text-xs"
                placeholder="params.subscription"
                value={d.field ?? ''}
                onChange={(e) => set(ev, { field: e.target.value })}
              />
            )}
            <button className="btn-ghost ml-auto px-3 py-1.5 text-xs" onClick={() => save(ev)}>
              {saved === ev ? 'Saved ✓' : 'Save'}
            </button>
          </div>
        )
      })}
    </div>
  )
}

function TemplatesEditor({ product, onChange }: { product: any; onChange: () => void }) {
  const [event, setEvent] = useState('signed_up')
  const [text, setText] = useState(() => JSON.stringify(product.event_templates?.[event] ?? {}, null, 2))
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  function pick(ev: string) {
    setEvent(ev)
    setText(JSON.stringify(product.event_templates?.[ev] ?? {}, null, 2))
    setSaved(false)
    setError('')
  }

  async function save() {
    setError('')
    try {
      const parsed = JSON.parse(text)
      await api.patch(`/api/admin/products/${product.id}`, { event_templates: { [event]: parsed } })
      setSaved(true)
      onChange()
    } catch (e: any) {
      setError(e.message.includes('JSON') ? 'Invalid JSON — fix the message body first.' : e.message)
    }
  }

  return (
    <div className="mt-5 space-y-3 border-t border-edge pt-5">
      <p className="text-sm text-fog">
        The exact message the product must POST for each event. These shapes are embedded in the
        integration prompt, and commission rules read fields out of them.
      </p>
      <div className="flex gap-2">
        {EVENTS.map((ev) => (
          <button key={ev} className={`btn-ghost px-3 py-1.5 text-xs ${event === ev ? 'border-mint/60 text-mint' : ''}`} onClick={() => pick(ev)}>
            {ev.replace('_', ' ')}
          </button>
        ))}
      </div>
      <textarea
        className="input h-56 w-full font-mono text-xs leading-relaxed"
        value={text}
        onChange={(e) => { setText(e.target.value); setSaved(false) }}
        spellCheck={false}
      />
      {error && <ErrorNote message={error} />}
      <button className="btn-primary px-4 py-1.5 text-sm" onClick={save}>{saved ? 'Saved ✓' : 'Save template'}</button>
    </div>
  )
}

/* ---------------- Users ---------------- */

function UsersTab() {
  const [users, setUsers] = useState<any[]>([])
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  function load() {
    api.get('/api/admin/users').then(setUsers)
  }
  useEffect(load, [])

  async function create(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const u = await api.post('/api/admin/users', form)
      setForm({ name: '', email: '', password: '' })
      setNotice(`Affiliate created with channel id ${u.affiliate_id}. They're auto-assigned to all your products — share their login with them, or use My Team → invite for self-serve signup.`)
      load()
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
                <th className="pb-3 pr-4">Channel id</th>
                <th className="pb-3 pr-4">Role</th>
                <th className="pb-3 pr-4">Level</th>
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
                  <td className="py-3 pr-4 font-mono text-xs text-mint">{u.affiliate_id}</td>
                  <td className="py-3 pr-4"><Chip status={u.role === 'admin' ? 'paid' : 'signed_up'} /></td>
                  <td className="py-3 pr-4 text-fog">{u.role === 'admin' ? 'root' : `L${u.depth}`}</td>
                  <td className="py-3 text-right font-display font-semibold text-gold">
                    {u.role === 'admin' ? '—' : inr(u.total_earned)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card h-fit p-6 rise">
        <h2 className="mb-1 font-display text-lg font-semibold">Add affiliate under you</h2>
        <p className="mb-4 text-xs text-fog">
          Creates an account directly below you (the root) with access to all your products. Their
          channel id is derived from their email.
        </p>
        <form onSubmit={create} className="space-y-3">
          <input className="input" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <input className="input" type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          <input className="input" type="password" placeholder="Temporary password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          {error && <ErrorNote message={error} />}
          <button className="btn-primary w-full">Create affiliate</button>
        </form>
        {notice && <p className="mt-4 text-xs text-leaf">{notice}</p>}
      </div>
    </div>
  )
}

/* ---------------- Payout requests ---------------- */

function PayoutsTab() {
  const [requests, setRequests] = useState<any[]>([])
  const [error, setError] = useState('')

  function load() {
    api.get('/api/admin/payout-requests').then(setRequests)
  }
  useEffect(load, [])

  async function act(id: number, action: 'approve' | 'mark-paid') {
    setError('')
    try {
      await api.post(`/api/admin/payout-requests/${id}/${action}`)
      load()
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div className="card p-6 rise">
      <h2 className="mb-1 font-display text-lg font-semibold">Payout requests</h2>
      <p className="mb-5 text-sm text-fog">
        Approve a request, make the payment manually to the account shown, then mark it paid —
        the affiliate gets an email confirmation automatically.
      </p>
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}
      {requests.length === 0 ? (
        <Empty>No payout requests yet.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                <th className="pb-3 pr-4">Request</th>
                <th className="pb-3 pr-4">Affiliate</th>
                <th className="pb-3 pr-4">Pay to</th>
                <th className="pb-3 pr-4 text-right">Amount</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id} className="border-b border-edge/50">
                  <td className="py-3 pr-4 font-mono text-xs">{r.number}</td>
                  <td className="py-3 pr-4">
                    <div className="font-medium">{r.user.name}</div>
                    <div className="text-xs text-fog">{r.user.email}</div>
                  </td>
                  <td className="py-3 pr-4 font-mono text-xs text-fog">
                    {r.bank_details.upi ||
                      [r.bank_details.bank_account, r.bank_details.ifsc].filter(Boolean).join(' · ') ||
                      '—'}
                  </td>
                  <td className="py-3 pr-4 text-right font-display font-semibold text-gold">{inr(r.amount)}</td>
                  <td className="py-3 pr-4"><Chip status={r.status} /></td>
                  <td className="py-3 text-right">
                    {r.status === 'requested' && (
                      <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => act(r.id, 'approve')}>Approve</button>
                    )}
                    {r.status === 'approved' && (
                      <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => act(r.id, 'mark-paid')}>Mark paid 💸</button>
                    )}
                    {r.status === 'paid' && r.paid_at && (
                      <span className="text-xs text-fog">paid {new Date(r.paid_at).toLocaleDateString()}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
