import { ShieldCheck, ShieldAlert, Zap, CheckCircle2 } from 'lucide-react'

const controls = [
  { label: 'Max automatic retries', value: '2' },
  { label: 'High-value threshold', value: '₹10,000' },
  { label: 'Unknown failure', value: 'Human approval required' },
  { label: 'Customer opted out', value: 'Automation blocked' },
  { label: 'Recovered transaction', value: 'Further action stopped' },
  { label: 'Synthetic batch', value: 'Real Razorpay actions disabled' },
]

export default function SafetyPanel() {
  return (
    <section className="panel safety-panel">
      <div className="panel-header section-header-row">
        <div>
          <span className="eyebrow">Agent Guardrails</span>
          <h3>Agent Guardrails</h3>
        </div>
        <ShieldCheck size={18} className="guard-shield" />
      </div>

      <div className="guard-status">
        <CheckCircle2 size={16} />
        <span>All guardrails active</span>
      </div>

      <div className="guard-list">
        {controls.map((item) => (
          <div key={item.label} className="guard-item">
            <div className="guard-icon">
              {item.label.includes('High-value') || item.label.includes('Unknown') ? <ShieldAlert size={16} /> : <Zap size={16} />}
            </div>
            <div className="guard-copy">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
