import { useEffect, useState } from 'react'
import { api, inr } from '../api'
import Layout from '../components/Layout'
import NetworkGraph from '../components/NetworkGraph'
import { Empty, Money, Stat } from '../components/ui'

export default function Network() {
  const [net, setNet] = useState<any>(null)

  useEffect(() => {
    api.get('/api/network').then(setNet)
  }, [])

  if (!net) return <Layout title="Your Network">{null}</Layout>

  const totalDirect = net.tree.direct_earnings

  return (
    <Layout title="Your Network">
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-3">
        <Stat label="Affiliates in your network" value={String(net.members.length)} accent="mint" />
        <Stat label="You earn directly" value={inr(totalDirect)} />
        <Stat
          label="Your network earns you"
          value={inr(net.network_earnings)}
          accent="gold"
          sub="20% override on every level below you"
        />
      </div>

      <div className="card mb-6 p-6 rise">
        <h2 className="mb-2 font-display text-lg font-semibold">Network map</h2>
        <p className="mb-6 text-sm text-fog">
          Every node shows what that affiliate adds to <i>your</i> earnings. Grow the tree,
          grow the passive income.
        </p>
        {net.members.length === 0 ? (
          <Empty>
            Your network is empty. Invite your first affiliate from the{' '}
            <a href="/team" className="text-mint">My Team</a> page and start earning overrides. 🌱
          </Empty>
        ) : (
          <NetworkGraph tree={net.tree} />
        )}
      </div>

      {net.members.length > 0 && (
        <div className="card p-6 rise">
          <h2 className="mb-5 font-display text-lg font-semibold">Leaderboard</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-edge text-left text-xs font-semibold uppercase tracking-wider text-fog">
                  <th className="pb-3 pr-4">Affiliate</th>
                  <th className="pb-3 pr-4">Level</th>
                  <th className="pb-3 pr-4 text-right">Their direct earnings</th>
                  <th className="pb-3 text-right">Earned for you</th>
                </tr>
              </thead>
              <tbody>
                {[...net.members]
                  .sort((a, b) => b.earned_for_me - a.earned_for_me)
                  .map((m, i) => (
                    <tr key={m.id} className="border-b border-edge/50">
                      <td className="py-3 pr-4">
                        <span className="mr-2 text-fog">{['🥇', '🥈', '🥉'][i] ?? `#${i + 1}`}</span>
                        <span className="font-medium">{m.name}</span>
                        <span className="ml-2 text-xs text-fog">{m.email}</span>
                      </td>
                      <td className="py-3 pr-4 text-fog">L{m.depth}</td>
                      <td className="py-3 pr-4 text-right text-fog">{inr(m.direct_earnings)}</td>
                      <td className="py-3 text-right"><Money amount={m.earned_for_me} /></td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Layout>
  )
}
