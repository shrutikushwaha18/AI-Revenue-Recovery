export default function RecoveryInsights({ metrics }) {
  const recoveredTransactions = Number(metrics?.recovered_transactions || 0)
  const totalTransactions = Number(metrics?.total_transactions || 0)
  const recoveredRevenue = Number(metrics?.total_revenue_recovered || 0)
  const riskRevenue = Number(metrics?.total_revenue_at_risk || 0)
  const humanEscalations = Number(metrics?.human_escalations || 0)
  const recoveryRate = Number(metrics?.recovery_rate_by_count || 0)
  const amountRate = Number(metrics?.recovery_rate_by_amount || 0)

  const insights = [
    `${humanEscalations} of ${totalTransactions} transactions required human escalation.`,
    `${recoveryRate.toFixed(0)}% of at-risk transactions were recovered.`,
    `₹${(recoveredRevenue / 100000).toFixed(2)}L of ₹${(riskRevenue / 100000).toFixed(2)}L simulated at-risk revenue was recovered.`,
    `${recoveredTransactions} successful recoveries were completed.`,
  ]

  return (
    <section className="panel insight-panel">
      <div className="panel-header section-header-row">
        <div>
          <span className="eyebrow">Recovery Insights</span>
          <h3>Recovery Insights</h3>
        </div>
      </div>
      <ul className="insight-list">
        {insights.map((insight) => (
          <li key={insight}>{insight}</li>
        ))}
      </ul>
    </section>
  )
}
