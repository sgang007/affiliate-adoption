import { FormEvent, useEffect, useState } from 'react'
import { api } from '../api'
import Layout from '../components/Layout'
import { Chip, Empty, ErrorNote } from '../components/ui'

const EVENTS = ['all', 'visited', 'signed_up', 'trial', 'subscribed']
const FORMATS = ['json', 'form']

export default function Settings() {
  const [endpoints, setEndpoints] = useState<any[]>([])
  const [url, setUrl] = useState('')
  const [eventType, setEventType] = useState('all')
  const [format, setFormat] = useState('json')
  const [error, setError] = useState('')

  function load() {
    api.get('/api/webhook-settings').then(setEndpoints)
  }
  useEffect(load, [])

  async function create(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/api/webhook-settings', { url, event_type: eventType, format })
      setUrl('')
      load()
    } catch (err: any) {
      setError(err.message)
    }
  }

  async function toggle(ep: any) {
    await api.patch(`/api/webhook-settings/${ep.id}`, { is_active: !ep.is_active })
    load()
  }

  async function remove(id: number) {
    await api.delete(`/api/webhook-settings/${id}`)
    load()
  }

  return (
    <Layout title="Webhook Settings">
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card p-6 lg:col-span-2 rise">
          <h2 className="mb-1 font-display text-lg font-semibold">Your callback endpoints</h2>
          <p className="mb-5 text-sm text-fog">
            Get notified at your own URL every time one of your referred users visits, signs up,
            starts a trial or subscribes. Payloads are HMAC-SHA256 signed with each endpoint's
            secret (header <code className="font-mono text-mint">X-Portal-Signature</code>).
          </p>
          {endpoints.length === 0 ? (
            <Empty>No endpoints configured — add one to receive funnel events in real time.</Empty>
          ) : (
            <div className="space-y-3">
              {endpoints.map((ep) => (
                <div key={ep.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-edge p-4">
                  <code className="min-w-0 flex-1 truncate font-mono text-sm text-mint">{ep.url}</code>
                  <Chip status={ep.event_type === 'all' ? 'subscribed' : ep.event_type} />
                  <span className="rounded-full bg-edge px-2.5 py-0.5 text-xs font-semibold text-fog">{ep.format}</span>
                  <span className={`text-xs font-semibold ${ep.is_active ? 'text-leaf' : 'text-fog'}`}>
                    {ep.is_active ? 'active' : 'paused'}
                  </span>
                  <div className="flex gap-2">
                    <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => toggle(ep)}>
                      {ep.is_active ? 'Pause' : 'Resume'}
                    </button>
                    <button className="btn-ghost px-3 py-1.5 text-xs hover:border-coral/60 hover:text-coral" onClick={() => remove(ep.id)}>
                      Delete
                    </button>
                  </div>
                  <div className="w-full font-mono text-xs text-fog">secret: {ep.secret}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card h-fit p-6 rise">
          <h2 className="mb-5 font-display text-lg font-semibold">Add endpoint</h2>
          <form onSubmit={create} className="space-y-4">
            <div>
              <label className="label">Callback URL</label>
              <input className="input" type="url" placeholder="https://your-server.com/hooks" value={url} onChange={(e) => setUrl(e.target.value)} required />
            </div>
            <div>
              <label className="label">Event</label>
              <select className="input" value={eventType} onChange={(e) => setEventType(e.target.value)}>
                {EVENTS.map((ev) => (
                  <option key={ev} value={ev}>{ev === 'all' ? 'All events' : ev.replace('_', ' ')}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Format</label>
              <select className="input" value={format} onChange={(e) => setFormat(e.target.value)}>
                {FORMATS.map((f) => (
                  <option key={f} value={f}>{f === 'json' ? 'JSON body' : 'Form-encoded'}</option>
                ))}
              </select>
            </div>
            {error && <ErrorNote message={error} />}
            <button className="btn-primary w-full">Add endpoint</button>
          </form>
        </div>
      </div>
    </Layout>
  )
}
