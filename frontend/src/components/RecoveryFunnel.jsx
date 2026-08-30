import { ArrowDown, CircleDollarSign } from 'lucide-react'

export default function RecoveryFunnel({ metrics, transactions = [] }) {
  const revenueAtRisk = Number(metrics?.total_revenue_at_risk || 0)
  const recovered = Number(metrics?.total_revenue_recovered || 0)
  const totalTransactions = Number(metrics?.total_transactions || 0)
  const recoveredCount = Number(metrics?.recovered_transactions || 0)
  const automatedAttempts = Math.max(0, transactions.filter((row) => row.recovery_attempted === 1).length)

  const steps = [
    { label: 'Revenue At Risk', value: `₹${(revenueAtRisk / 100000).toFixed(2)}L` },
    { label: 'Transactions Evaluated', value: totalTransactions },
    { label: 'Automated Recovery Attempts', value: automatedAttempts },
    { label: 'Successful Recoveries', value: recoveredCount },
    { label: 'Simulated Revenue Recovered', value: `₹${(recovered / 100000).toFixed(2)}L` },
  ]

  return (
    <section className="panel funnel-panel">
      <div className="panel-header section-header-row">
        <div>
          <span className="eyebrow">Revenue Recovery Funnel</span>
          <h3>Revenue Recovery Funnel</h3>
        </div>
        <div className="funnel-icon"><CircleDollarSign size={18} /></div>
      </div>

      <div className="funnel-steps">
        {steps.map((step, index) => (
          <div key={step.label} className="funnel-step">
            <div className="funnel-value">{step.value}</div>
            <div className="funnel-label">{step.label}</div>
            {index < steps.length - 1 && <ArrowDown size={16} className="funnel-arrow" />}
          </div>
        ))}
      </div>
    </section>
  )
}
