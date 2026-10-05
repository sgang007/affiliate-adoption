import { FormEvent, useEffect, useState } from 'react'
import { api, inr } from '../api'
import Layout from '../components/Layout'
import { Chip, CopyField, Empty, ErrorNote, Money } from '../components/ui'

export default function Team() {
  const [team, setTeam] = useState<any[]>([])
  const [invites, setInvites] = useState<any[]>([])
  const [email, setEmail] = useState('')
  const [lastInvite, setLastInvite] = useState<any>(null)
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
      setLastInvite(res)
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
            <h2 className="mb-1 font-display text-lg font-semibold">Team performance</h2>
            <p className="mb-5 text-sm text-fog">
              What each affiliate you recruited is pulling in — their funnel, their earnings, and
              your cut from their whole branch.
            </p>
            {team.length === 0 ? (
              <Empty>Nobody on your team yet — invite someone and earn a cut of everything they make. 💰</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                      <th className="pb-3 pr-4">Affiliate</th>
                      <th className="pb-3 pr-3 text-right">Visits</th>
                      <th className="pb-3 pr-3 text-right">Signups</th>
                      <th className="pb-3 pr-3 text-right">Trials</th>
                      <th className="pb-3 pr-3 text-right">Subs</th>
                      <th className="pb-3 pr-3 text-right">Branch</th>
                      <th className="pb-3 pr-3 text-right">They earned</th>
                      <th className="pb-3 text-right">Your cut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {team.map((m) => (
                      <tr key={m.id} className="border-b border-edge/50">
                        <td className="py-3 pr-4">
                          <div className="font-medium">{m.name}</div>
                          <div className="text-xs text-fog">
                            {m.email} · joined {new Date(m.joined).toLocaleDateString()}
                          </div>
                        </td>
                        <td className="py-3 pr-3 text-right font-display">{m.stats.visits}</td>
                        <td className="py-3 pr-3 text-right font-display text-mint">{m.stats.signed_up}</td>
                        <td className="py-3 pr-3 text-right font-display text-gold">{m.stats.trial}</td>
                        <td className="py-3 pr-3 text-right font-display text-leaf">{m.stats.subscribed}</td>
                        <td className="py-3 pr-3 text-right text-fog">{m.subtree_size}</td>
                        <td className="py-3 pr-3 text-right text-fog">{inr(m.their_direct_earnings)}</td>
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
              <h2 className="mb-5 font-display text-lg font-semibold">Invites</h2>
              <div className="space-y-4">
                {invites.map((i) => (
                  <div key={i.id} className="flex flex-wrap items-center gap-3">
                    <div className="w-56 min-w-0 truncate font-medium">{i.email}</div>
                    <Chip status={i.accepted ? 'subscribed' : 'pending'} />
                    <span className="text-xs text-fog">
                      {i.accepted
                        ? 'joined your team ✓'
                        : `invited ${new Date(i.created_at).toLocaleDateString()}`}
                    </span>
                    {!i.accepted && (
                      <div className="w-full sm:w-auto sm:flex-1">
                        <CopyField value={i.invite_url} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="card h-fit p-6 shadow-glow rise">
          <h2 className="mb-1 font-display text-lg font-semibold">Recruit an affiliate</h2>
          <p className="mb-5 text-sm text-fog">
            They get their own links and dashboard; you earn the network commission on every
            conversion in their branch — forever.
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
              {lastInvite.email_sent ? (
                <p className="mb-2 text-xs text-leaf">
                  Invite emailed to {lastInvite.email} ✓ — you can also share the link directly:
                </p>
              ) : (
                <p className="mb-2 text-xs text-gold">
                  ⚠ Email isn't configured on this server, so no invite email was sent. Share
                  this signup link with them yourself:
                </p>
              )}
              <CopyField value={lastInvite.invite_url} />
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
