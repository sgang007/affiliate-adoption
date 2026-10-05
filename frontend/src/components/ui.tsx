import { ReactNode, useState } from 'react'
import { inr } from '../api'

export function Stat({ label, value, accent, sub }: { label: string; value: string; accent?: 'mint' | 'gold'; sub?: string }) {
  return (
    <div className="card p-5 rise">
      <div className="text-xs font-semibold uppercase tracking-wider text-fog">{label}</div>
      <div
        className={`mt-1.5 font-display text-3xl font-bold ${
          accent === 'gold' ? 'text-gold' : accent === 'mint' ? 'text-mint' : 'text-snow'
        }`}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-sm text-fog">{sub}</div>}
    </div>
  )
}

const STATUS_STYLE: Record<string, string> = {
  visited: 'bg-edge text-fog',
  signed_up: 'bg-mint/15 text-mint',
  trial: 'bg-gold/15 text-gold',
  subscribed: 'bg-leaf/15 text-leaf',
  renewal: 'bg-leaf/15 text-leaf',
  churned: 'bg-coral/15 text-coral',
  pending: 'bg-gold/15 text-gold',
  draft: 'bg-edge text-fog',
  submitted: 'bg-mint/15 text-mint',
  invoiced: 'bg-mint/15 text-mint',
  paid: 'bg-leaf/15 text-leaf',
}

export function Chip({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLE[status] ?? 'bg-edge text-fog'}`}>
      {status.replace('_', ' ')}
    </span>
  )
}

export function CopyField({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div>
      {label && <div className="label">{label}</div>}
      <div className="flex items-center gap-2">
        <code className="flex-1 truncate rounded-xl bg-ink border border-edge px-3 py-2 font-mono text-sm text-mint">
          {value}
        </code>
        <button
          className="btn-ghost px-3 py-2 text-sm"
          onClick={() => {
            navigator.clipboard.writeText(value)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
          }}
        >
          {copied ? 'Copied ✓' : 'Copy'}
        </button>
      </div>
    </div>
  )
}

export function Funnel({ visits, signed_up, trial, subscribed }: { visits: number; signed_up: number; trial: number; subscribed: number }) {
  const max = Math.max(visits, 1)
  const rows = [
    { label: 'Visited', n: visits, color: 'bg-fog/50' },
    { label: 'Signed up', n: signed_up, color: 'bg-mint' },
    { label: 'On trial', n: trial, color: 'bg-gold' },
    { label: 'Subscribed', n: subscribed, color: 'bg-leaf' },
  ]
  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-3">
          <div className="w-24 shrink-0 text-sm text-fog">{r.label}</div>
          <div className="h-3 flex-1 overflow-hidden rounded-full bg-ink">
            <div
              className={`h-full rounded-full ${r.color} transition-all duration-500`}
              style={{ width: `${Math.max((r.n / max) * 100, r.n > 0 ? 3 : 0)}%` }}
            />
          </div>
          <div className="w-12 shrink-0 text-right font-display font-semibold">{r.n}</div>
        </div>
      ))}
    </div>
  )
}

export function Money({ amount }: { amount: number }) {
  return <span className="font-display font-semibold text-gold">{inr(amount)}</span>
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-10 text-center text-fog">{children}</div>
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="rounded-xl border border-coral/40 bg-coral/10 px-4 py-2.5 text-sm text-coral">{message}</div>
}
