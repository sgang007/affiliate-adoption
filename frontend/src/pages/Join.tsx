import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, setSession } from '../api'
import { ErrorNote } from '../components/ui'

export default function Join() {
  const { token } = useParams()
  const [invite, setInvite] = useState<any>(null)
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    api
      .get(`/api/auth/invite/${token}`)
      .then(setInvite)
      .catch((e) => setError(e.message))
  }, [token])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await api.post('/api/auth/accept-invite', { token, name, password })
      setSession(res.token, res.user)
      navigate('/')
    } catch (err: any) {
      setError(err.message || 'Could not create account')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="card w-full max-w-md p-8 rise">
        <div className="mb-2 font-display text-2xl font-bold">
          Join the <span className="text-mint">network</span>
        </div>
        {invite ? (
          <p className="mb-8 text-sm text-fog">
            <span className="text-snow font-medium">{invite.inviter_name}</span> invited{' '}
            <span className="text-snow font-medium">{invite.email}</span> to their affiliate
            network. Set up your account to get your own referral links and start earning.
          </p>
        ) : (
          !error && <p className="mb-8 text-sm text-fog">Loading invite…</p>
        )}
        {invite && (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label">Your name</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
            </div>
            <div>
              <label className="label">Choose a password</label>
              <input className="input" type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            {error && <ErrorNote message={error} />}
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? 'Creating account…' : 'Claim my spot →'}
            </button>
          </form>
        )}
        {!invite && error && <ErrorNote message={error} />}
      </div>
    </div>
  )
}
