import { ArrowDown, TrendingUp } from 'lucide-react'

export default function RevenueImpact({ metrics }) {
  const revenueAtRisk = Number(metrics?.total_revenue_at_risk || 0)
  const recovered = Number(metrics?.total_revenue_recovered || 0)
  const recoveryRate = Number(metrics?.recovery_rate_by_amount || 0)
  const recoveredCount = Number(metrics?.recovered_transactions || 0)
  const totalTransactions = Number(metrics?.total_transactions || 0)
  const progress = Math.min(100, Math.max(0, recoveryRate))

  return (
    <section className="panel impact-panel">
      <div className="panel-header section-header-row">
        <div>
          <span className="eyebrow">Synthetic Evaluation</span>
          <h3>Revenue Impact</h3>
        </div>
        <div className="impact-trend"><TrendingUp size={16} /> <span>{recoveryRate.toFixed(2)}%</span></div>
      </div>

      <div className="impact-grid">
        <div className="impact-metric emphasis">
          <label>Revenue At Risk</label>
          <strong>{new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(revenueAtRisk)}</strong>
        </div>
        <div className="impact-metric emphasis success">
          <label>Simulated Revenue Recovered</label>
          <strong>{new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(recovered)}</strong>
        </div>
        <div className="impact-metric emphasis alt">
          <label>Recovery Rate</label>
          <strong>{recoveryRate.toFixed(2)}%</strong>
        </div>
      </div>

      <div className="recovery-progress-wrap">
        <div className="recovery-progress-bar">
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-meta">
          <span>{recoveredCount} of {totalTransactions} transactions recovered</span>
          <span>{recoveryRate.toFixed(2)}%</span>
        </div>
      </div>

      <div className="impact-footnote">
        <ArrowDown size={14} />
        <span>Estimated revenue recovery performance</span>
      </div>
    </section>
  )
}
