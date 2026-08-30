import { ShieldCheck, Sparkles } from 'lucide-react'

export default function Header() {
  return (
    <header className="topbar">
      <div>
        <div className="eyebrow-row">
          <Sparkles size={14} />
          <span>RecoverAI</span>
        </div>
        <h1>RecoverAI</h1>
        <p className="subtitle">Autonomous Revenue Recovery Agent</p>
      </div>

      <div className="brand-badge">
        <ShieldCheck size={18} />
        <span>Detect. Decide. Recover. Verify.</span>
      </div>
    </header>
  )
}
