import { FormEvent, useEffect, useState } from 'react'
import { api, currentUser, inr } from '../api'
import Layout from '../components/Layout'
import { Chip, Empty, ErrorNote, Stat } from '../components/ui'

export default function Payouts() {
  const [summary, setSummary] = useState<any>(null)
  const [ledger, setLedger] = useState<any[]>([])
  const [form, setForm] = useState({ upi: '', bank_account: '', ifsc: '', account_name: '' })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const isAdmin = currentUser()?.role === 'admin'

  function load() {
    api.get('/api/payouts').then((s) => {
      setSummary(s)
      setForm((f) => ({ ...f, ...s.saved_details }))
    })
    api.get('/api/payouts/ledger').then(setLedger)
  }
  useEffect(load, [])

  async function requestPayout(e: FormEvent) {
    e.preventDefault()
    setError('')
    setNotice('')
    try {
      const req = await api.post('/api/payouts/request', form)
      setNotice(`Payout ${req.number} requested for ${inr(req.amount)}. The admin will review and pay it in the next cycle.`)
      load()
    } catch (err: any) {
      setError(err.message)
    }
  }

  if (!summary) return <Layout title="Payouts">{null}</Layout>

  return (
    <Layout title="Payouts">
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Available to withdraw" value={inr(summary.balance_pending)} accent="gold" />
        <Stat label="In review" value={inr(summary.in_review)} />
        <Stat label="Paid out" value={inr(summary.total_paid)} accent="mint" />
        <Stat label="Lifetime earned" value={inr(summary.total_earned)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="card p-6 rise">
            <h2 className="mb-5 font-display text-lg font-semibold">Payout requests</h2>
            {notice && (
              <div className="mb-4 rounded-xl border border-leaf/40 bg-leaf/10 px-4 py-2.5 text-sm text-leaf">{notice}</div>
            )}
            {summary.requests.length === 0 ? (
              <Empty>No payout requests yet. Earn, then cash out below. 💰</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                      <th className="pb-3 pr-4">Request</th>
                      <th className="pb-3 pr-4 text-right">Amount</th>
                      <th className="pb-3 pr-4">Status</th>
                      <th className="pb-3 text-right">Paid on</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.requests.map((r: any) => (
                      <tr key={r.id} className="border-b border-edge/50">
                        <td className="py-3 pr-4 font-mono text-xs">{r.number}</td>
                        <td className="py-3 pr-4 text-right font-display font-semibold text-gold">{inr(r.amount)}</td>
                        <td className="py-3 pr-4"><Chip status={r.status} /></td>
                        <td className="py-3 text-right text-fog">
                          {r.paid_at ? new Date(r.paid_at).toLocaleDateString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card p-6 rise">
            <h2 className="mb-5 font-display text-lg font-semibold">Earnings ledger</h2>
            {ledger.length === 0 ? (
              <Empty>Your ledger is empty — share your referral links to start earning.</Empty>
            ) : (
              <div className="max-h-96 overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-panel">
                    <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                      <th className="pb-3 pr-4">When</th>
                      <th className="pb-3 pr-4">Product</th>
                      <th className="pb-3 pr-4">Event</th>
                      <th className="pb-3 pr-4">Kind</th>
                      <th className="pb-3 pr-4 text-right">Amount</th>
                      <th className="pb-3">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.map((e) => (
                      <tr key={e.id} className="border-b border-edge/50">
                        <td className="py-2.5 pr-4 text-fog">{new Date(e.created_at).toLocaleDateString()}</td>
                        <td className="py-2.5 pr-4">{e.product}</td>
                        <td className="py-2.5 pr-4"><Chip status={e.event_type} /></td>
                        <td className="py-2.5 pr-4 text-xs text-fog">{e.is_direct ? 'direct' : 'network'}</td>
                        <td className="py-2.5 pr-4 text-right font-display font-semibold text-gold">{inr(e.amount)}</td>
                        <td className="py-2.5"><Chip status={e.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {!isAdmin && (
          <div className="card h-fit p-6 shadow-gold rise">
            <h2 className="mb-1 font-display text-lg font-semibold">Request payout</h2>
            <p className="mb-5 text-sm text-fog">
              Withdraws your full pending balance of{' '}
              <b className="text-gold">{inr(summary.balance_pending)}</b>. Add a UPI id or bank
              account — the admin reviews, pays, and you get an email confirmation.
            </p>
            <form onSubmit={requestPayout} className="space-y-3">
              <div>
                <label className="label">UPI id</label>
                <input className="input" placeholder="you@upi" value={form.upi} onChange={(e) => setForm({ ...form, upi: e.target.value })} />
              </div>
              <div className="text-center text-xs text-fog">— or bank transfer —</div>
              <div>
                <label className="label">Account number</label>
                <input className="input" value={form.bank_account} onChange={(e) => setForm({ ...form, bank_account: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">IFSC</label>
                  <input className="input" value={form.ifsc} onChange={(e) => setForm({ ...form, ifsc: e.target.value })} />
                </div>
                <div>
                  <label className="label">Account name</label>
                  <input className="input" value={form.account_name} onChange={(e) => setForm({ ...form, account_name: e.target.value })} />
                </div>
              </div>
              {error && <ErrorNote message={error} />}
              <button className="btn-primary w-full" disabled={summary.balance_pending <= 0}>
                Request {inr(summary.balance_pending)} 💸
              </button>
            </form>
          </div>
        )}
      </div>
    </Layout>
  )
}
