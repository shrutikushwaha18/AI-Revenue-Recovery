import { AlertTriangle, ArrowRightLeft, Clock3, ShieldAlert } from 'lucide-react'

const cards = [
  {
    key: 'retry',
    title: 'Retry',
    count: '10 transactions',
    text: 'Temporary technical failures',
    icon: Clock3,
  },
  {
    key: 'payment_link',
    title: 'Payment Link',
    count: '24 transactions',
    text: 'Issuer declines & abandoned checkout',
    icon: ArrowRightLeft,
  },
  {
    key: 'payment_link_later',
    title: 'Pay Later',
    count: '10 transactions',
    text: 'Insufficient balance scenarios',
    icon: Clock3,
  },
  {
    key: 'human_review',
    title: 'Human Review',
    count: '56 transactions',
    text: 'High-value / unsafe automation cases',
    icon: ShieldAlert,
  },
]

export default function AgentDecisionCenter({ breakdown = {} }) {
  const normalized = cards.map((card) => ({
    ...card,
    count: `${Number(breakdown[card.key] || 0)} transactions`,
  }))

  return (
    <section className="panel decision-panel">
      <div className="panel-header section-header-row">
        <div>
          <span className="eyebrow">AI Recovery Decision Center</span>
          <h3>Agent Decision Center</h3>
        </div>
      </div>

      <div className="decision-grid">
        {normalized.map(({ key, title, count, text, icon: Icon }) => (
          <div key={key} className="decision-card">
            <div className="decision-icon">
              <Icon size={18} />
            </div>
            <div>
              <div className="decision-title">{title}</div>
              <div className="decision-count">{count}</div>
            </div>
            <p>{text}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
