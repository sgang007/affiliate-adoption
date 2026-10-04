import { FormEvent, useEffect, useState } from 'react'
import { api, inr } from '../api'
import Layout from '../components/Layout'
import { Chip, Empty, ErrorNote } from '../components/ui'

function currentPeriod() {
  return new Date().toISOString().slice(0, 7)
}

export default function Payouts() {
  const [invoices, setInvoices] = useState<any[]>([])
  const [period, setPeriod] = useState(currentPeriod())
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  function load() {
    api.get('/api/invoices').then(setInvoices)
  }
  useEffect(load, [])

  async function generate(e: FormEvent) {
    e.preventDefault()
    setError('')
    setNotice('')
    try {
      const inv = await api.post('/api/invoices/generate', { period })
      setNotice(`Bill ${inv.number} generated for ${inr(inv.total_amount)}. Submit it to request payout.`)
      load()
    } catch (err: any) {
      setError(err.message)
    }
  }

  async function submit(id: number) {
    setError('')
    try {
      await api.post(`/api/invoices/${id}/submit`)
      setNotice('Bill submitted — it will be paid in the next monthly payout cycle.')
      load()
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <Layout title="Payouts">
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card p-6 lg:col-span-2 rise">
          <h2 className="mb-5 font-display text-lg font-semibold">Your bills</h2>
          {error && <div className="mb-4"><ErrorNote message={error} /></div>}
          {notice && (
            <div className="mb-4 rounded-xl border border-leaf/40 bg-leaf/10 px-4 py-2.5 text-sm text-leaf">{notice}</div>
          )}
          {invoices.length === 0 ? (
            <Empty>No bills yet. Generate your first monthly bill once you have commissions. 🧾</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                    <th className="pb-3 pr-4">Bill</th>
                    <th className="pb-3 pr-4">Period</th>
                    <th className="pb-3 pr-4 text-right">Amount</th>
                    <th className="pb-3 pr-4">Status</th>
                    <th className="pb-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((i) => (
                    <tr key={i.id} className="border-b border-edge/50">
                      <td className="py-3 pr-4 font-mono text-xs">{i.number}</td>
                      <td className="py-3 pr-4">{i.period}</td>
                      <td className="py-3 pr-4 text-right font-display font-semibold text-gold">{inr(i.total_amount)}</td>
                      <td className="py-3 pr-4"><Chip status={i.status} /></td>
                      <td className="py-3 text-right">
                        {i.status === 'draft' && (
                          <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => submit(i.id)}>
                            Submit for payout →
                          </button>
                        )}
                        {i.status === 'paid' && i.paid_at && (
                          <span className="text-xs text-fog">paid {new Date(i.paid_at).toLocaleDateString()}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card h-fit p-6 rise">
          <h2 className="mb-1 font-display text-lg font-semibold">Generate monthly bill</h2>
          <p className="mb-5 text-sm text-fog">
            Bundles all pending commissions for a month into one bill. Submit it and the company
            pays everyone in the monthly payout cycle.
          </p>
          <form onSubmit={generate} className="space-y-4">
            <div>
              <label className="label">Period</label>
              <input className="input" type="month" value={period} onChange={(e) => setPeriod(e.target.value)} required />
            </div>
            <button className="btn-primary w-full">Generate bill 🧾</button>
          </form>
        </div>
      </div>
    </Layout>
  )
}
