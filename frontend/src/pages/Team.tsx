import { FormEvent, useEffect, useState } from 'react'
import { api, inr } from '../api'
import Layout from '../components/Layout'
import { CopyField, Empty, ErrorNote, Money } from '../components/ui'

export default function Team() {
  const [team, setTeam] = useState<any[]>([])
  const [invites, setInvites] = useState<any[]>([])
  const [email, setEmail] = useState('')
  const [lastInvite, setLastInvite] = useState<string>('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function load() {
    api.get('/api/team').then(setTeam)
    api.get('/api/team/invites').then(setInvites)
  }
  useEffect(load, [])

  async function invite(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await api.post('/api/team/invite', { email })
      setLastInvite(res.invite_url)
      setEmail('')
      load()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Layout title="My Team">
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="card p-6 rise">
            <h2 className="mb-5 font-display text-lg font-semibold">Your affiliates</h2>
            {team.length === 0 ? (
              <Empty>Nobody on your team yet — invite someone and earn 20% of everything they make. 💰</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                      <th className="pb-3 pr-4">Affiliate</th>
                      <th className="pb-3 pr-4">Their network</th>
                      <th className="pb-3 pr-4 text-right">They earned</th>
                      <th className="pb-3 text-right">You earned from them</th>
                    </tr>
                  </thead>
                  <tbody>
                    {team.map((m) => (
                      <tr key={m.id} className="border-b border-edge/50">
                        <td className="py-3 pr-4">
                          <div className="font-medium">{m.name}</div>
                          <div className="text-xs text-fog">{m.email} · joined {new Date(m.joined).toLocaleDateString()}</div>
                        </td>
                        <td className="py-3 pr-4 text-fog">{m.subtree_size} member{m.subtree_size === 1 ? '' : 's'}</td>
                        <td className="py-3 pr-4 text-right text-fog">{inr(m.their_direct_earnings)}</td>
                        <td className="py-3 text-right"><Money amount={m.earned_for_me} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {invites.length > 0 && (
            <div className="card p-6 rise">
              <h2 className="mb-5 font-display text-lg font-semibold">Pending invites</h2>
              <div className="space-y-3">
                {invites
                  .filter((i) => !i.accepted)
                  .map((i) => (
                    <div key={i.id} className="flex items-center justify-between gap-4 text-sm">
                      <span className="font-medium">{i.email}</span>
                      <code className="truncate font-mono text-xs text-fog">{i.invite_url}</code>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>

        <div className="card h-fit p-6 shadow-glow rise">
          <h2 className="mb-1 font-display text-lg font-semibold">Recruit an affiliate</h2>
          <p className="mb-5 text-sm text-fog">
            They get their own links and dashboard. You get <b className="text-gold">20% of every
            commission</b> they ever earn — and it cascades down their network too.
          </p>
          <form onSubmit={invite} className="space-y-4">
            <div>
              <label className="label">Email address</label>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            {error && <ErrorNote message={error} />}
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? 'Sending…' : 'Send invite 🚀'}
            </button>
          </form>
          {lastInvite && (
            <div className="mt-5 border-t border-edge pt-5">
              <p className="mb-2 text-xs text-fog">Invite created — share this link directly:</p>
              <CopyField value={lastInvite} />
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
