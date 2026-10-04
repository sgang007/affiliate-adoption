// Gamification: XP from funnel progress, named ranks, next-level progress.
export interface Funnel {
  visits: number
  signed_up: number
  trial: number
  subscribed: number
}

export function xpFrom(funnel: Funnel, networkSize: number): number {
  return (
    funnel.visits * 1 +
    funnel.signed_up * 10 +
    funnel.trial * 25 +
    funnel.subscribed * 100 +
    networkSize * 40
  )
}

export const RANKS = [
  { at: 0, name: 'Spark', icon: '✦', blurb: 'Every empire starts with one link.' },
  { at: 120, name: 'Igniter', icon: '🔥', blurb: 'Your network is catching fire.' },
  { at: 400, name: 'Operator', icon: '⚡', blurb: 'Conversions are becoming routine.' },
  { at: 1000, name: 'Rainmaker', icon: '🌧', blurb: 'Subscriptions rain on your dashboard.' },
  { at: 2500, name: 'Architect', icon: '🏛', blurb: 'You build networks, not just links.' },
  { at: 6000, name: 'Legend', icon: '👑', blurb: 'The network bows to you.' },
]

export function rankFor(xp: number) {
  let idx = 0
  for (let i = 0; i < RANKS.length; i++) if (xp >= RANKS[i].at) idx = i
  const rank = RANKS[idx]
  const next = RANKS[idx + 1] ?? null
  const progress = next ? Math.min((xp - rank.at) / (next.at - rank.at), 1) : 1
  return { rank, next, progress, xp }
}
