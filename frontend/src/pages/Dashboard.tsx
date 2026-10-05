import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, inr } from '../api'
import Layout from '../components/Layout'
import { CopyField, Empty, Funnel, Stat } from '../components/ui'
import { rankFor, xpFrom } from '../gamify'

export default function Dashboard() {
  const [dash, setDash] = useState<any>(null)
  const [products, setProducts] = useState<any[]>([])

  useEffect(() => {
    api.get('/api/dashboard').then(setDash)
    api.get('/api/products').then(setProducts)
  }, [])

  if (!dash) return <Layout title="Dashboard">{null}</Layout>

  const { rank, next, progress, xp } = rankFor(xpFrom(dash.funnel, dash.network_size))

  return (
    <Layout title="Dashboard">
      {/* Referral links — the first thing to see and share */}
      {products.length > 0 && (
        <div className="card mb-6 border-mint/30 p-6 shadow-glow rise">
          <h2 className="font-display text-lg font-semibold">
            🔗 Your referral link{products.length > 1 ? 's' : ''} — share to earn
          </h2>
          <p className="mb-5 mt-1 text-sm text-fog">
            Send this link to your network. Every signup, trial and subscription that comes
            through it pays you automatically — and when you recruit affiliates from{' '}
            <Link to="/team" className="text-mint">My Team</Link>, their conversions earn you a
            cut too.
          </p>
          <div className="space-y-4">
            {products.map((p) => (
              <CopyField key={p.id} label={p.name} value={p.link.referral_url} />
            ))}
          </div>
        </div>
      )}
      {/* Rank banner */}
      <div className="card mb-6 flex flex-col gap-5 p-6 shadow-glow md:flex-row md:items-center rise">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-mint/10 text-3xl">
          {rank.icon}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-display text-2xl font-bold text-mint">{rank.name}</span>
            <span className="text-sm text-fog">{xp.toLocaleString()} XP · {rank.blurb}</span>
          </div>
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-ink">
            <div className="h-full rounded-full bg-mint transition-all duration-700" style={{ width: `${progress * 100}%` }} />
          </div>
          {next && (
            <div className="mt-1.5 text-xs text-fog">
              {next.at - xp} XP to <span className="text-snow">{next.name} {next.icon}</span>
            </div>
          )}
        </div>
        <div className="text-right">
          <div className="text-xs font-semibold uppercase tracking-wider text-fog">Network</div>
          <div className="font-display text-3xl font-bold">{dash.network_size}</div>
          <div className="text-xs text-fog">affiliates under you</div>
        </div>
      </div>

      {/* Earnings */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Total earned" value={inr(dash.earnings.total)} accent="gold" />
        <Stat label={`This month (${dash.period})`} value={inr(dash.earnings.this_month)} />
        <Stat label="From my referrals" value={inr(dash.earnings.direct)} accent="mint" />
        <Stat label="From my network" value={inr(dash.earnings.network)} sub="20% overrides, all levels" />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Funnel */}
        <div className="card p-6 lg:col-span-2 rise">
          <h2 className="mb-5 font-display text-lg font-semibold">Acquisition funnel</h2>
          <Funnel {...dash.funnel} />
          <div className="mt-5 border-t border-edge pt-4 text-sm text-fog">
            Pending payout: <span className="font-semibold text-gold">{inr(dash.earnings.pending)}</span>
            <span className="mx-2">·</span>
            Paid out: <span className="font-semibold text-leaf">{inr(dash.earnings.paid)}</span>
          </div>
        </div>

        {/* Products */}
        <div className="lg:col-span-3">
          <h2 className="mb-4 font-display text-lg font-semibold">Your products</h2>
          {products.length === 0 && (
            <div className="card">
              <Empty>No products assigned yet. Ask your admin to add you to a campaign.</Empty>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            {products.map((p) => (
              <Link key={p.id} to={`/products/${p.id}`} className="card group p-5 transition-colors duration-150 hover:border-mint/60 rise">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-display text-lg font-semibold group-hover:text-mint transition-colors duration-150">
                    {p.name}
                  </div>
                  <span className="shrink-0 rounded-full bg-gold/15 px-2.5 py-0.5 text-xs font-semibold text-gold">
                    {(() => {
                      const sub = p.rules?.find((r: any) => r.event === 'subscribed' && r.value > 0)
                      return sub ? (sub.type === 'commission' ? `${sub.value}% rec.` : `₹${sub.value}/sub`) : 'earn ₹'
                    })()}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-fog">{p.description}</p>
                <div className="mt-4 flex gap-4 text-sm">
                  <span><b className="font-display">{p.stats.visits}</b> <span className="text-fog">visits</span></span>
                  <span><b className="font-display">{p.stats.signed_up}</b> <span className="text-fog">signups</span></span>
                  <span><b className="font-display text-leaf">{p.stats.subscribed}</b> <span className="text-fog">subs</span></span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}
