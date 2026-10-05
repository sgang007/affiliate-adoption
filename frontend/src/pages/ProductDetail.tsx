import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, inr } from '../api'
import Layout from '../components/Layout'
import { Chip, CopyField, Empty, Funnel, Money, Stat } from '../components/ui'

export default function ProductDetail() {
  const { id } = useParams()
  const [product, setProduct] = useState<any>(null)
  const [referrals, setReferrals] = useState<any[]>([])

  useEffect(() => {
    api.get(`/api/products/${id}`).then(setProduct)
    api.get(`/api/products/${id}/referrals`).then(setReferrals)
  }, [id])

  if (!product) return <Layout title="Product">{null}</Layout>

  const totalEarned = referrals.reduce((s, r) => s + r.earned, 0)

  return (
    <Layout title={product.name}>
      <Link to="/" className="mb-6 inline-block text-sm text-fog hover:text-mint transition-colors duration-150">
        ← Back to dashboard
      </Link>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* Referral link */}
          <div className="card p-6 shadow-glow rise">
            <h2 className="mb-1 font-display text-lg font-semibold">Your referral link</h2>
            <p className="mb-5 text-sm text-fog">
              Share it anywhere. The <code className="font-mono text-mint">?channel</code> tag is
              cookied on every visit, so you get credit for signups, trials and subscriptions —
              whenever they happen.
            </p>
            <div className="space-y-4">
              <CopyField label="Referral link (direct to product)" value={product.link.referral_url} />
              <CopyField label="Tracked link (counts visits via the portal)" value={product.link.tracking_url} />
            </div>
          </div>

          {/* Referred users */}
          <div className="card p-6 rise">
            <div className="mb-5 flex items-baseline justify-between">
              <h2 className="font-display text-lg font-semibold">People you brought in</h2>
              <span className="text-sm text-fog">earned <Money amount={totalEarned} /></span>
            </div>
            {referrals.length === 0 ? (
              <Empty>No referrals yet. Share your link and watch this fill up. 🚀</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                      <th className="pb-3 pr-4">User</th>
                      <th className="pb-3 pr-4">Status</th>
                      <th className="pb-3 pr-4">Subscription</th>
                      <th className="pb-3 pr-4 text-right">You earned</th>
                      <th className="pb-3 text-right">Last update</th>
                    </tr>
                  </thead>
                  <tbody>
                    {referrals.map((r) => (
                      <tr key={r.id} className="border-b border-edge/50">
                        <td className="py-3 pr-4">
                          <div className="font-medium">{r.email || r.external_id}</div>
                          {r.email && <div className="font-mono text-xs text-fog">{r.external_id}</div>}
                        </td>
                        <td className="py-3 pr-4"><Chip status={r.status} /></td>
                        <td className="py-3 pr-4 text-fog">
                          {r.subscription_amount ? `${inr(r.subscription_amount)}/mo` : '—'}
                        </td>
                        <td className="py-3 pr-4 text-right"><Money amount={r.earned} /></td>
                        <td className="py-3 text-right text-fog">
                          {r.last_update ? new Date(r.last_update).toLocaleDateString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <div className="card p-6 rise">
            <h2 className="mb-5 font-display text-lg font-semibold">Funnel</h2>
            <Funnel {...product.stats} visits={product.stats.visits} />
          </div>
          <div className="card p-6 rise">
            <h2 className="mb-1 font-display text-lg font-semibold">Incentive rules</h2>
            <p className="mb-4 text-xs text-fog">
              Pool per event — you keep the remainder after each upline level takes{' '}
              {product.network_commission_pct}%.
            </p>
            <div className="space-y-3">
              {product.rules
                .filter((r: any) => r.value > 0)
                .map((r: any) => (
                  <div key={r.event} className="flex items-center justify-between text-sm">
                    <span className="capitalize text-fog">{r.event.replace('_', ' ')}</span>
                    <span className="font-display font-semibold text-gold">
                      {r.type === 'flat'
                        ? inr(r.value)
                        : `${r.value}% of subscription${r.event === 'renewal' ? ' /mo' : ''}`}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
