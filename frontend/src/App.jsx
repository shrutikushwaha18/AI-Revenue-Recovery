import { useEffect, useMemo, useState } from 'react'
import { Activity, BrainCircuit, ShieldCheck, TrendingUp } from 'lucide-react'
import Header from './components/Header'
import MetricCard from './components/MetricCard'
import LiveRecoveryCard from './components/LiveRecoveryCard'
import RecoveryBreakdownChart from './components/RecoveryBreakdownChart'
import OutcomeBreakdownChart from './components/OutcomeBreakdownChart'
import TransactionTable from './components/TransactionTable'
import SafetyPanel from './components/SafetyPanel'
import LoadingState from './components/LoadingState'
import ErrorState from './components/ErrorState'
import { fetchJson } from './services/api'
import { formatCurrency, formatPercent } from './utils/formatters'
import './App.css'

const ACTION_ORDER = ['human_review', 'payment_link', 'payment_link_later', 'retry', 'stop']
const OUTCOME_ORDER = ['successful', 'human_review', 'failed', 'pending', 'stopped']

function App() {
  const [metrics, setMetrics] = useState(null)
  const [recoveryBreakdown, setRecoveryBreakdown] = useState({})
  const [outcomeBreakdown, setOutcomeBreakdown] = useState({})
  const [transactions, setTransactions] = useState([])
  const [liveTransaction, setLiveTransaction] = useState(null)
  const [auditLogs, setAuditLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        setLoading(true)
        setError('')

        const [metricsData, recoveryData, outcomeData, batchTransactionsData, allTransactionsData, auditData] = await Promise.all([
          fetchJson('/api/dashboard/metrics'),
          fetchJson('/api/dashboard/recovery-breakdown'),
          fetchJson('/api/dashboard/outcome-breakdown'),
          fetchJson('/api/batch/transactions'),
          fetchJson('/api/transactions'),
          fetchJson('/api/audit/TXN005'),
        ])

        setMetrics(metricsData)
        setRecoveryBreakdown(recoveryData?.breakdown || {})
        setOutcomeBreakdown(outcomeData || {})
        setTransactions(batchTransactionsData?.transactions || [])

        const tx = (allTransactionsData || []).find((row) => row.transaction_id === 'TXN005') || null
        setLiveTransaction(tx)
        setAuditLogs(auditData || [])
      } catch (err) {
        setError(err?.response?.data?.error || err?.message || 'Failed to load dashboard data.')
      } finally {
        setLoading(false)
      }
    }

    loadDashboard()
  }, [])

  const actionChartData = useMemo(
    () =>
      ACTION_ORDER.map((key) => ({
        name: key,
        value: Number(recoveryBreakdown[key] || 0),
      })),
    [recoveryBreakdown],
  )

  const outcomeChartData = useMemo(
    () =>
      OUTCOME_ORDER.map((key) => ({
        name: key,
        value: Number(outcomeBreakdown[key] || 0),
      })),
    [outcomeBreakdown],
  )

  if (loading) {
    return (
      <div className="page-shell">
        <LoadingState message="Loading RecoverAI analytics..." />
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-shell">
        <ErrorState message={error} />
      </div>
    )
  }

  return (
    <div className="page-shell">
      <Header />

      <main className="dashboard">
        <section className="section-block">
          <div className="section-header-row">
            <div>
              <span className="eyebrow">Synthetic 100-Transaction Evaluation</span>
              <h2>Metrics</h2>
            </div>
            <div className="muted-note">Simulated revenue — not real merchant money.</div>
          </div>

          <div className="metrics-grid">
            <MetricCard title="Total Transactions" value={metrics?.total_transactions ?? 0} accent="blue" />
            <MetricCard title="Total Revenue at Risk" value={formatCurrency(metrics?.total_revenue_at_risk)} accent="amber" />
            <MetricCard title="Total Revenue Recovered" value={formatCurrency(metrics?.total_revenue_recovered)} accent="green" />
            <MetricCard title="Recovery Rate by Amount" value={formatPercent(metrics?.recovery_rate_by_amount)} accent="violet" />
            <MetricCard title="Recovery Rate by Count" value={formatPercent(metrics?.recovery_rate_by_count)} accent="teal" />
            <MetricCard title="Human Escalations" value={metrics?.human_escalations ?? 0} accent="rose" />
          </div>
        </section>

        <section className="section-block">
          <LiveRecoveryCard transaction={liveTransaction} auditLogs={auditLogs} />
        </section>

        <section className="section-block charts-grid">
          <div className="panel">
            <div className="panel-header section-header-row">
              <h3>Recovery Action Breakdown</h3>
              <Activity size={18} />
            </div>
            <RecoveryBreakdownChart data={actionChartData} />
          </div>

          <div className="panel">
            <div className="panel-header section-header-row">
              <h3>Final Outcome Breakdown</h3>
              <TrendingUp size={18} />
            </div>
            <OutcomeBreakdownChart data={outcomeChartData} />
          </div>
        </section>

        <section className="section-block table-layout">
          <TransactionTable transactions={transactions} />
          <SafetyPanel />
        </section>

        <section className="section-block footer-note">
          <div className="footer-chip">
            <BrainCircuit size={16} />
            <span>Autonomous decisioning with bounded controls and verified execution.</span>
          </div>
          <div className="footer-chip success-chip">
            <ShieldCheck size={16} />
            <span>Live recovery flow stays isolated from synthetic evaluation.</span>
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
