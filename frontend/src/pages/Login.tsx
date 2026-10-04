import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setSession } from '../api'
import { ErrorNote } from '../components/ui'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await api.post('/api/auth/login', { email, password })
      setSession(res.token, res.user)
      navigate('/')
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="card w-full max-w-md p-8 rise">
        <div className="mb-2 font-display text-2xl font-bold">
          <span className="text-mint">Adoption</span> HQ
        </div>
        <p className="mb-8 text-sm text-fog">
          Turn your network into a growth engine. Sign in to track referrals, build your
          affiliate team and watch the earnings stack up.
        </p>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </div>
          <div>
            <label className="label">Password</label>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error && <ErrorNote message={error} />}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? 'Signing in…' : 'Enter the arena →'}
          </button>
        </form>
      </div>
    </div>
  )
}
