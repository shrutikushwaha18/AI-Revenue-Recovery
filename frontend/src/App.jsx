import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  ArrowUpRight,
  BrainCircuit,
  Check,
  ChevronDown,
  Command,
  Download,
  FileText,
  Play,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react'
import Header from './components/Header'
import HeroStatus from './components/HeroStatus'
import RevenueImpact from './components/RevenueImpact'
import LiveRecoveryCard from './components/LiveRecoveryCard'
import AgentDecisionCenter from './components/AgentDecisionCenter'
import RecoveryBreakdownChart from './components/RecoveryBreakdownChart'
import OutcomeBreakdownChart from './components/OutcomeBreakdownChart'
import RecoveryFunnel from './components/RecoveryFunnel'
import AgentActivityFeed from './components/AgentActivityFeed'
import RecoveryInsights from './components/RecoveryInsights'
import TransactionTable from './components/TransactionTable'
import TransactionDrawer from './components/TransactionDrawer'
import SafetyPanel from './components/SafetyPanel'
import LoadingState from './components/LoadingState'
import ErrorState from './components/ErrorState'
import { api, fetchJson } from './services/api'
import './App.css'

const ACTION_ORDER = ['human_review', 'payment_link', 'payment_link_later', 'retry', 'stop']
const OUTCOME_ORDER = ['successful', 'human_review', 'failed', 'pending', 'stopped']
const ORDERED_STAGES = ['Failed Payment', 'AI Decision', 'Payment Link', 'Customer Paid', 'Signed Webhook', 'Revenue Recovered']

const cmp = (a, b) => Number(b.amount || 0) - Number(a.amount || 0)

function App() {
  const [metrics, setMetrics] = useState(null)
  const [recoveryBreakdown, setRecoveryBreakdown] = useState({})
  const [outcomeBreakdown, setOutcomeBreakdown] = useState({})
  const [transactions, setTransactions] = useState([])
  const [liveTransaction, setLiveTransaction] = useState(null)
  const [auditLogs, setAuditLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedRow, setSelectedRow] = useState(null)
  const [openLiveProof, setOpenLiveProof] = useState(false)
  const [openHumanReview, setOpenHumanReview] = useState(false)
  const [openChartDrill, setOpenChartDrill] = useState(null)
  const [commandOpen, setCommandOpen] = useState(false)
  const [commandQuery, setCommandQuery] = useState('')
  const [activeChip, setActiveChip] = useState(null)
  const [exportOpen, setExportOpen] = useState(false)
  const [floatingMenuOpen, setFloatingMenuOpen] = useState(false)
  const [demoOpen, setDemoOpen] = useState(false)
  const [demoStep, setDemoStep] = useState(0)
  const [simulationOpen, setSimulationOpen] = useState(false)
  const [simulationProgress, setSimulationProgress] = useState(0)
  const [simulationStage, setSimulationStage] = useState(0)
  const [toasts, setToasts] = useState([])
  const commandInputRef = useRef(null)
  const initialToastRendered = useRef(false)

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
      setError(err?.response?.data?.error || err?.message || 'Unable to reach RecoverAI backend')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  useEffect(() => {
    if (metrics && !initialToastRendered.current) {
      initialToastRendered.current = true
      showToast('Batch analysis completed', 'Live and synthetic recovery data refreshed.')
    }
  }, [metrics])

  useEffect(() => {
    const handleKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen(true)
      }

      if (event.key === 'Escape') {
        setSelectedRow(null)
        setOpenLiveProof(false)
        setOpenHumanReview(false)
        setOpenChartDrill(null)
        setCommandOpen(false)
        setSimulationOpen(false)
        setDemoOpen(false)
      }
    }

    const handlePointerMove = (event) => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
      const x = (event.clientX / window.innerWidth) * 100
      const y = (event.clientY / window.innerHeight) * 100
      document.documentElement.style.setProperty('--spotlight-x', `${x}%`)
      document.documentElement.style.setProperty('--spotlight-y', `${y}%`)
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('pointermove', handlePointerMove)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('pointermove', handlePointerMove)
    }
  }, [])

  const showToast = (title, message) => {
    const id = Date.now() + Math.random()
    setToasts((current) => [...current, { id, title, message }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, 2600)
  }

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

  const humanReviewTransactions = useMemo(
    () => transactions.filter((row) => (row.recovery_action || row.final_recovery_status || row.recovery_status || '').toLowerCase() === 'human_review' || (row.final_recovery_status || row.recovery_status || '').toLowerCase() === 'human_review'),
    [transactions],
  )

  const humanReviewValue = useMemo(
    () => humanReviewTransactions.reduce((sum, row) => sum + Number(row.amount || 0), 0),
    [humanReviewTransactions],
  )

  const highValueCases = useMemo(
    () => [...transactions].sort(cmp).slice(0, 10),
    [transactions],
  )

  const commandItems = useMemo(() => {
    const query = commandQuery.trim().toLowerCase()
    const items = [
      { label: 'View Live Recovery', description: 'Open TXN005 proof flow', action: 'live' },
      { label: 'Open Human Review Queue', description: 'Review gated transactions', action: 'human' },
      { label: 'Show High Value Transactions', description: 'Top 10 revenue risk cases', action: 'highvalue' },
      { label: 'Jump to Recovery Analytics', description: 'Go to charts and outcomes', action: 'analytics' },
      { label: 'Jump to Transactions', description: 'Go to ledger', action: 'transactions' },
      { label: 'Export Batch CSV', description: 'Download current batch data', action: 'export' },
    ]

    if (!query) return items
    return items.filter((item) => `${item.label} ${item.description}`.toLowerCase().includes(query))
  }, [commandQuery])

  const runCommandAction = (action) => {
    setCommandOpen(false)
    setCommandQuery('')

    if (action === 'live') {
      setOpenLiveProof(true)
    }
    if (action === 'human') {
      setOpenHumanReview(true)
    }
    if (action === 'highvalue') {
      setSelectedRow(highValueCases[0] || null)
    }
    if (action === 'analytics') {
      document.getElementById('recovery-analytics')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    if (action === 'transactions') {
      document.getElementById('transactions-table')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    if (action === 'export') {
      exportBatchCsv()
    }
  }

  const exportBatchCsv = () => {
    if (!transactions.length) return

    const rows = [
      ['transaction_id', 'customer_name', 'amount', 'failure_reason', 'recovery_action', 'recovery_reason', 'retry_count', 'final_recovery_status', 'recovered_amount'],
      ...transactions.map((row) => [
        row.transaction_id || '',
        row.customer_name || '',
        Number(row.amount || 0),
        row.failure_reason || '',
        row.recovery_action || '',
        row.recovery_reason || '',
        Number(row.retry_count || 0),
        row.final_recovery_status || row.recovery_status || '',
        Number(row.recovered_amount || 0),
      ]),
    ]

    const csv = rows.map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'recoverai-batch-export.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  const exportAuditJson = () => {
    const blob = new Blob([JSON.stringify(auditLogs, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'recoverai-audit.json'
    link.click()
    URL.revokeObjectURL(url)
  }

  const runSimulation = async () => {
    const stages = ['Evaluating transaction risks', 'Applying recovery policies', 'Simulating bounded interventions', 'Calculating outcomes']

    setSimulationOpen(true)
    setSimulationProgress(0)
    setSimulationStage(0)

    const stepInterval = window.setInterval(() => {
      setSimulationStage((current) => Math.min(stages.length - 1, current + 1))
    }, 700)

    const progressInterval = window.setInterval(() => {
      setSimulationProgress((current) => {
        const next = Math.min(100, current + 18)
        if (next >= 100) {
          window.clearInterval(progressInterval)
        }
        return next
      })
    }, 280)

    try {
      await api.post('/api/batch/analyze')
      await loadDashboard()
      showToast('Recovery successful', 'Synthetic simulation refreshed with real backend results.')
      setSimulationProgress(100)
    } catch (err) {
      setError(err?.response?.data?.error || err?.message || 'Recovery simulation failed.')
      showToast('Simulation failed', 'Unable to complete the recovery analysis.')
    } finally {
      window.clearInterval(stepInterval)
      window.setTimeout(() => {
        setSimulationOpen(false)
      }, 1000)
    }
  }

  const startDemo = () => {
    setDemoOpen(true)
    setDemoStep(0)
  }

  const demoSteps = [
    {
      title: 'Revenue Problem',
      body: 'The dashboard tracks failed payments, customer drop-off, and recoverable value before any intervention is attempted.',
    },
    {
      title: '100 Transaction AI Evaluation',
      body: 'Every synthetic batch case is evaluated with bounded automation, policy guardrails, and triage rules.',
    },
    {
      title: 'Recovery Decision Distribution',
      body: 'The action mix shows where retries, links, and human reviews are triggered based on policy thresholds.',
    },
    {
      title: 'Live Razorpay TXN005 Recovery',
      body: 'TXN005 demonstrates the real recovery journey: failed payment, decisioning, payment link, and webhook-signed recovery.',
    },
    {
      title: 'Signed Webhook + Audit Proof',
      body: 'Webhook verification and audit history provide evidence that the recovery was executed and confirmed.',
    },
    {
      title: 'Measured Recovery Impact',
      body: 'Actual totals, rates, and recovered value show the impact without altering the backend contract.',
    },
  ]

  const currentDemo = demoSteps[demoStep]

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
        <ErrorState message={error} onRetry={loadDashboard} />
      </div>
    )
  }

  return (
    <div className="page-shell">
      <Header
        statusChips={[
          { label: 'Agent Online', info: 'Agent decisioning and monitoring is active.' },
          { label: 'Razorpay Connected', info: 'Live payment proof is connected to Razorpay Test Mode.' },
          { label: 'Policy Guard Active', info: 'Recovery policies remain bounded and reviewable.' },
          { label: `${transactions.length || 0} Transactions Evaluated`, info: 'Synthetic batch evaluation is fully loaded.' },
        ]}
        onChipClick={(label) => {
          const map = {
            'Agent Online': 'Agent decisioning and monitoring is active.',
            'Razorpay Connected': 'Live payment proof is connected to Razorpay Test Mode.',
            'Policy Guard Active': 'Recovery policies remain bounded and reviewable.',
          }
          setActiveChip(map[label] || label)
        }}
        onExportMenuOpen={setExportOpen}
        exportOpen={exportOpen}
        onExportCsv={exportBatchCsv}
        onExportAudit={exportAuditJson}
        onStartDemo={startDemo}
        onRunSimulation={runSimulation}
      />

      {activeChip && (
        <div className="chip-popover">
          <div className="chip-popover-inner">
            <strong>Status</strong>
            <span>{activeChip}</span>
          </div>
        </div>
      )}

      <main className="dashboard">
        <section className="hero-layout panel" id="recovery-analytics">
          <div className="hero-copy">
            <div className="eyebrow-row">
              <span className="eyebrow-inline">RecoverAI</span>
            </div>
            <h1>RecoverAI</h1>
            <h2>Autonomous Revenue Recovery Agent</h2>
            <p>
              Detect revenue leakage. Decide the safest recovery path. Recover and verify automatically.
            </p>
            <div className="hero-actions">
              <button type="button" className="primary-button" onClick={runSimulation}>Run Recovery Simulation</button>
              <button type="button" className="secondary-button" onClick={startDemo}>Start Demo</button>
            </div>
          </div>
          <HeroStatus />
        </section>

        <RevenueImpact metrics={metrics} />

        <section className="section-block">
          <LiveRecoveryCard transaction={liveTransaction} auditLogs={auditLogs} onOpen={() => setOpenLiveProof(true)} />
        </section>

        <AgentDecisionCenter breakdown={recoveryBreakdown} onOpenHumanReview={() => setOpenHumanReview(true)} />

        <section className="section-block charts-grid">
          <div className="panel chart-panel">
            <div className="panel-header section-header-row">
              <div>
                <span className="eyebrow">Recovery Actions</span>
                <h3>Recovery Actions</h3>
              </div>
            </div>
            <RecoveryBreakdownChart data={actionChartData} total={actionChartData.reduce((sum, item) => sum + item.value, 0)} onSegmentClick={(key) => setOpenChartDrill(key)} />
          </div>

          <div className="panel chart-panel">
            <div className="panel-header section-header-row">
              <div>
                <span className="eyebrow">Final Outcomes</span>
                <h3>Final Outcomes</h3>
              </div>
            </div>
            <OutcomeBreakdownChart data={outcomeChartData} />
          </div>
        </section>

        <RecoveryFunnel metrics={metrics} transactions={transactions} />

        <section className="insight-grid">
          <AgentActivityFeed transactions={transactions} auditLogs={auditLogs} />
          <RecoveryInsights metrics={metrics} />
        </section>

        <section className="section-block table-layout" id="transactions-table">
          <TransactionTable transactions={transactions} onSelectRow={setSelectedRow} />
          <SafetyPanel />
        </section>

        <section className="section-block footer-note">
          <div className="footer-chip">
            <BrainCircuit size={16} />
            <span>RecoverAI AI Revenue Recovery • Razorpay Test Mode</span>
          </div>
          <div className="footer-chip success-chip">
            <ShieldCheck size={16} />
            <span>Batch results are synthetic evaluation. Live payment proof uses Razorpay Test Mode.</span>
          </div>
        </section>
      </main>

      {selectedRow && <TransactionDrawer row={selectedRow} onClose={() => setSelectedRow(null)} />}

      {openLiveProof && (
        <div className="custom-modal-overlay" onClick={() => setOpenLiveProof(false)}>
          <div className="custom-modal glass-modal live-proof-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="eyebrow">Live Razorpay Test Recovery</div>
                <h3>LIVE RAZORPAY TEST RECOVERY</h3>
              </div>
              <button type="button" className="icon-button" onClick={() => setOpenLiveProof(false)} aria-label="Close preview">
                <X size={16} />
              </button>
            </div>

            <div className="proof-grid">
              <div className="proof-card">
                <div className="proof-row"><span>TXN005</span><strong>{liveTransaction?.transaction_id || 'TXN005'}</strong></div>
                <div className="proof-row"><span>Amount</span><strong>₹{Number(liveTransaction?.amount || 3499).toLocaleString('en-IN')}</strong></div>
                <div className="proof-row"><span>Failure Reason</span><strong>{liveTransaction?.failure_reason || 'Bank Decline'}</strong></div>
                <div className="proof-row"><span>Recovery Action</span><strong>{liveTransaction?.recovery_action || 'Payment Link'}</strong></div>
                <div className="proof-row"><span>Status</span><strong className="status-good">{liveTransaction?.status || 'RECOVERED'}</strong></div>
              </div>

              <div className="proof-journey" aria-label="Recovery journey timeline">
                {ORDERED_STAGES.map((stage, index) => {
                  const done = index < ORDERED_STAGES.indexOf('Revenue Recovered') || (stage === 'Revenue Recovered' && (auditLogs.some((item) => /revenue_recovered|recovered/i.test(item.action || item.reason || '')) || (liveTransaction?.status || '').toLowerCase() === 'recovered'))
                  return (
                    <div key={stage} className={`journey-step ${done ? 'done' : ''}`}>
                      <span className="journey-icon">{done ? <Check size={14} /> : <ArrowUpRight size={14} />}</span>
                      <span>{stage}</span>
                    </div>
                  )
                })}
              </div>
            </div>

            {(auditLogs.some((item) => /revenue_recovered|recovered/i.test(item.action || item.reason || '')) || (liveTransaction?.status || '').toLowerCase() === 'recovered') && (
              <div className="verified-badge">
                <ShieldCheck size={16} />
                <span>Signed Webhook Verified</span>
              </div>
            )}
          </div>
        </div>
      )}

      {openHumanReview && (
        <div className="custom-modal-overlay" onClick={() => setOpenHumanReview(false)}>
          <div className="custom-modal glass-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="eyebrow">Human Review Queue</div>
                <h3>Human Approval Queue</h3>
              </div>
              <button type="button" className="icon-button" onClick={() => setOpenHumanReview(false)} aria-label="Close queue">
                <X size={16} />
              </button>
            </div>

            <div className="queue-summary">
              <div>
                <span>Total Transactions</span>
                <strong>{humanReviewTransactions.length}</strong>
              </div>
              <div>
                <span>Value Gated</span>
                <strong>₹{humanReviewValue.toLocaleString('en-IN')}</strong>
              </div>
            </div>

            <div className="list-wrap">
              {highValueCases.slice(0, 10).map((row) => (
                <div key={row.transaction_id} className="queue-row">
                  <div>
                    <strong>{row.transaction_id}</strong>
                    <p>{row.reason || row.recovery_reason || row.failure_reason || 'Manual approval required'}</p>
                  </div>
                  <div className="queue-meta">
                    <span>₹{Number(row.amount || 0).toLocaleString('en-IN')}</span>
                    <span>Retry {row.retry_count ?? 0}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {openChartDrill && (
        <div className="custom-modal-overlay" onClick={() => setOpenChartDrill(null)}>
          <div className="custom-modal glass-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="eyebrow">Recovery Action Drilldown</div>
                <h3>{openChartDrill}</h3>
              </div>
              <button type="button" className="icon-button" onClick={() => setOpenChartDrill(null)} aria-label="Close drilldown">
                <X size={16} />
              </button>
            </div>

            <div className="list-wrap">
              {transactions.filter((row) => (row.recovery_action || '').toLowerCase() === openChartDrill.toLowerCase()).map((row) => (
                <div key={row.transaction_id} className="queue-row" onClick={() => setSelectedRow(row)}>
                  <div>
                    <strong>{row.transaction_id}</strong>
                    <p>{row.customer_name || 'Customer'}</p>
                  </div>
                  <div className="queue-meta">
                    <span>₹{Number(row.amount || 0).toLocaleString('en-IN')}</span>
                    <span>{row.recovery_status || row.final_recovery_status || 'pending'}</span>
                  </div>
                </div>
              )) || <p>No matching transactions.</p>}
            </div>
          </div>
        </div>
      )}

      {simulationOpen && (
        <div className="custom-modal-overlay" onClick={() => setSimulationOpen(false)}>
          <div className="custom-modal glass-modal simulation-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="eyebrow">Synthetic Simulation</div>
                <h3>Simulation Complete</h3>
              </div>
              <button type="button" className="icon-button" onClick={() => setSimulationOpen(false)} aria-label="Close simulation">
                <X size={16} />
              </button>
            </div>

            <div className="progress-track">
              <span style={{ width: `${simulationProgress}%` }} />
            </div>

            <ul className="simulation-steps">
              {['Evaluating transaction risks', 'Applying recovery policies', 'Simulating bounded interventions', 'Calculating outcomes'].map((step, index) => (
                <li key={step} className={index <= simulationStage ? 'active' : ''}>
                  <span>{index <= simulationStage ? <Check size={14} /> : <Play size={12} />}</span>
                  {step}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {demoOpen && (
        <div className="custom-modal-overlay demo-overlay" onClick={() => setDemoOpen(false)}>
          <div className="custom-modal glass-modal demo-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="eyebrow">RecoverAI Demo</div>
                <h3>{currentDemo.title}</h3>
              </div>
              <button type="button" className="icon-button" onClick={() => setDemoOpen(false)} aria-label="Close demo">
                <X size={16} />
              </button>
            </div>

            <p className="demo-body">{currentDemo.body}</p>
            <div className="demo-progress">
              {demoSteps.map((step, index) => (
                <span key={step.title} className={index === demoStep ? 'active' : ''} />
              ))}
            </div>
            <div className="demo-actions">
              <button type="button" className="secondary-button" onClick={() => setDemoStep((current) => Math.max(0, current - 1))} disabled={demoStep === 0}>Previous</button>
              <button type="button" className="primary-button" onClick={() => {
                if (demoStep < demoSteps.length - 1) {
                  setDemoStep((current) => current + 1)
                } else {
                  setDemoOpen(false)
                }
              }}>
                {demoStep === demoSteps.length - 1 ? 'Exit Demo' : 'Next'}
              </button>
            </div>
          </div>
        </div>
      )}

      {commandOpen && (
        <div className="command-overlay" onClick={() => setCommandOpen(false)}>
          <div className="command-palette" onClick={(event) => event.stopPropagation()}>
            <div className="command-search-row">
              <Search size={16} />
              <input
                ref={commandInputRef}
                value={commandQuery}
                onChange={(event) => setCommandQuery(event.target.value)}
                placeholder="Search commands..."
                aria-label="Command palette search"
              />
            </div>
            <div className="command-list">
              {commandItems.map((item, index) => (
                <button key={item.label} type="button" className="command-item" onClick={() => runCommandAction(item.action)}>
                  <span>{item.label}</span>
                  <small>{item.description}</small>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="floating-agent">
        <button type="button" className="agent-fab" onClick={() => setFloatingMenuOpen((current) => !current)} aria-label="Open agent menu">
          <Sparkles size={18} />
          Agent
          <ChevronDown size={14} />
        </button>
        {floatingMenuOpen && (
          <div className="agent-menu">
            <button type="button" onClick={() => { setFloatingMenuOpen(false); setOpenLiveProof(true) }}>Live Recovery</button>
            <button type="button" onClick={() => { setFloatingMenuOpen(false); setOpenHumanReview(true) }}>Human Review</button>
            <button type="button" onClick={() => { setFloatingMenuOpen(false); setSelectedRow(highValueCases[0] || null) }}>Highest Revenue Risk</button>
            <button type="button" onClick={() => { setFloatingMenuOpen(false); document.getElementById('recovery-analytics')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }}>Recovery Analytics</button>
            <button type="button" onClick={() => { setFloatingMenuOpen(false); exportBatchCsv() }}>Export Report</button>
          </div>
        )}
      </div>

      <div className="toast-stack">
        {toasts.map((toast) => (
          <div key={toast.id} className="toast-item">
            <strong>{toast.title}</strong>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default App
