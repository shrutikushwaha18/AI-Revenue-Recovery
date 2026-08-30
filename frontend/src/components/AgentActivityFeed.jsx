import { Clock3, ArrowUpRight } from 'lucide-react'

export default function AgentActivityFeed({ transactions = [], auditLogs = [] }) {
  const items = [
    ...auditLogs.slice(0, 3).map((row) => ({
      id: `audit-${row.id || row.action}`,
      title: row.transaction_id || 'TXN005',
      description: row.reason || 'System activity',
      meta: `${row.action}`,
    })),
    ...transactions.slice(0, 4).map((row) => ({
      id: `batch-${row.transaction_id}`,
      title: row.transaction_id,
      description: row.recovery_reason || row.failure_reason || 'Decision logged',
      meta: `${row.recovery_action || 'pending'} • ₹${Number(row.amount || 0).toLocaleString('en-IN')}`,
    })),
  ].slice(0, 6)

  return (
    <section className="panel feed-panel">
      <div className="panel-header section-header-row">
        <div>
          <span className="eyebrow">Recent Agent Activity</span>
          <h3>Recent Agent Activity</h3>
        </div>
        <Clock3 size={18} />
      </div>

      <div className="feed-list">
        {items.map((item) => (
          <div key={item.id} className="feed-item">
            <div className="feed-bullet"><ArrowUpRight size={12} /></div>
            <div className="feed-copy">
              <div className="feed-title">{item.title}</div>
              <div className="feed-desc">{item.description}</div>
            </div>
            <div className="feed-meta">{item.meta}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
