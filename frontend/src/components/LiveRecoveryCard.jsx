import { ArrowRight, CheckCircle2, ShieldAlert, ShieldCheck } from 'lucide-react'

const flow = [
  'Failed Payment',
  'AI Decision',
  'Payment Link',
  'Razorpay Payment',
  'Signed Webhook',
  'Revenue Recovered',
]

export default function LiveRecoveryCard({ transaction, auditLogs }) {
  return (
    <section className="panel live-panel">
      <div className="panel-header section-header-row">
        <div>
          <span className="eyebrow">Live Razorpay Test Mode</span>
          <h3>Payment Recovery Proof</h3>
        </div>
        <div className="status-pill success">
          <CheckCircle2 size={16} />
          <span>Verified</span>
        </div>
      </div>

      <div className="live-grid">
        <div className="detail-card">
          <div className="detail-row"><span>Transaction</span><strong>{transaction?.transaction_id || '—'}</strong></div>
          <div className="detail-row"><span>Customer</span><strong>{transaction?.customer_name || '—'}</strong></div>
          <div className="detail-row"><span>Amount</span><strong>{transaction ? `₹${Number(transaction.amount || 0).toLocaleString('en-IN')}` : '—'}</strong></div>
          <div className="detail-row"><span>Failure reason</span><strong>{transaction?.failure_reason || '—'}</strong></div>
          <div className="detail-row"><span>Recovery action</span><strong>{transaction?.recovery_action || '—'}</strong></div>
          <div className="detail-row"><span>Recovery status</span><strong>{transaction?.recovery_status || '—'}</strong></div>
          <div className="detail-row"><span>Recovered amount</span><strong>{transaction ? `₹${Number(transaction.recovered_amount || 0).toLocaleString('en-IN')}` : '—'}</strong></div>
        </div>

        <div className="flow-card">
          {flow.map((step, index) => (
            <div key={step} className="flow-step">
              <div className="flow-icon">
                {index === flow.length - 1 ? <ShieldCheck size={16} /> : index === 0 ? <ShieldAlert size={16} /> : <ArrowRight size={16} />}
              </div>
              <span>{step}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="audit-panel">
        <h4>Audit Timeline</h4>
        <div className="timeline">
          {auditLogs && auditLogs.length ? auditLogs.map((event, index) => (
            <div key={`${event.action}-${index}`} className="timeline-item">
              <div className="timeline-dot" />
              <div>
                <strong>{event.action}</strong>
                <p>{event.reason}</p>
              </div>
            </div>
          )) : <p>No audit entries available.</p>}
        </div>
      </div>
    </section>
  )
}
