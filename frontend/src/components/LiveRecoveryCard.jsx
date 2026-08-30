import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  Check,
  CheckCircle2,
  Clock3,
  Coins,
  Link2,
  ShieldCheck,
  Sparkles,
  UserCheck,
  X,
} from 'lucide-react'

const toDisplayLabel = (value) => {
  const source = String(value || '').replace(/_/g, ' ')
  return source
    .split(' ')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

const hasAuditAction = (auditLogs, matcher) =>
  (auditLogs || []).some((entry) => {
    const action = String(entry?.action || entry?.reason || '').toLowerCase()
    return matcher.test(action)
  })

const formatTimestamp = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString('en-IN', { hour12: false })
}

const getRecoveryState = (transaction, auditLogs) => {
  const status = String(transaction?.status || transaction?.recovery_status || '').toLowerCase()
  const recoveredAmount = Number(transaction?.recovered_amount || 0)
  const hasRecoveredEvent = hasAuditAction(auditLogs, /revenue_recovered|payment link successfully paid|payment_link_paid/i)

  if (status === 'recovered' && recoveredAmount > 0 && hasRecoveredEvent) {
    return {
      state: 'verified',
      title: 'Verified End-to-End Recovery',
      badge: 'VERIFIED',
      badgeClass: 'verified',
      subtitle: 'Signed Webhook Verified',
      footer: '✓ END-TO-END RECOVERY VERIFIED',
      label: 'Verified',
    }
  }

  if (status === 'failed' || status === 'human_review' || status === 'stopped') {
    return {
      state: 'failed',
      title: 'Recovery Requires Attention',
      badge: 'ATTENTION REQUIRED',
      badgeClass: 'attention',
      subtitle: 'Recovery requires a policy or manual review',
      footer: null,
      label: 'Attention required',
    }
  }

  return {
    state: 'pending',
    title: 'Recovery In Progress',
    badge: 'IN PROGRESS',
    badgeClass: 'pending',
    subtitle: 'Real recovery execution through Razorpay Test Mode',
    footer: null,
    label: 'In progress',
  }
}

export default function LiveRecoveryCard({ transaction, auditLogs = [] }) {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const status = String(transaction?.status || transaction?.recovery_status || '').toLowerCase()
  const recoveredAmount = Number(transaction?.recovered_amount || 0)
  const originalAmount = Number(transaction?.amount || 0)
  const hasRecoveredEvent = hasAuditAction(auditLogs, /revenue_recovered|payment link successfully paid|payment_link_paid/i)
  const hasDecision = Boolean(transaction?.recovery_action)
  const hasPaymentLink = Boolean(transaction?.payment_link || transaction?.payment_link_id || hasAuditAction(auditLogs, /payment_link_created|payment link/i))
  const hasFailure = Boolean(transaction?.failure_reason)
  const recoveryState = useMemo(() => getRecoveryState(transaction, auditLogs), [transaction, auditLogs])

  useEffect(() => {
    if (!isModalOpen) return undefined

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setIsModalOpen(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isModalOpen])

  const recoveryProgress = recoveryState.state === 'verified' ? 100 : originalAmount > 0 ? Math.min(100, (recoveredAmount / originalAmount) * 100) : 0
  const latestSuccessfulEvent = [...auditLogs].reverse().find((entry) => /revenue_recovered|payment link successfully paid|payment_link_paid/i.test(String(entry?.action || entry?.reason || '')))
  const verificationChecks = [
    { label: 'Agent Decision Recorded', ok: hasDecision },
    { label: 'Razorpay Payment Link Created', ok: hasPaymentLink },
    { label: 'Signed Webhook Processed', ok: hasRecoveredEvent },
    { label: 'Revenue Recovery Recorded', ok: recoveryState.state === 'verified' },
  ]

  const stages = [
    {
      key: 'failed_payment',
      title: 'Failed Payment',
      description: 'Bank decline detected',
      done: hasFailure || status === 'failed' || status === 'recovered',
      icon: AlertTriangle,
      failed: recoveryState.state === 'failed' && !recoveredAmount,
    },
    {
      key: 'ai_decision',
      title: 'AI Decision',
      description: 'Payment link selected',
      done: hasDecision,
      icon: BrainCircuit,
      failed: false,
    },
    {
      key: 'payment_link',
      title: 'Payment Link Created',
      description: 'Recovery link generated through Razorpay',
      done: hasPaymentLink,
      icon: Link2,
      failed: false,
    },
    {
      key: 'customer_paid',
      title: 'Customer Paid',
      description: 'Payment link completed successfully',
      done: recoveredAmount > 0 || status === 'recovered',
      icon: UserCheck,
      failed: false,
    },
    {
      key: 'webhook_verified',
      title: 'Webhook Verified',
      description: 'Signed Razorpay event received',
      done: hasRecoveredEvent || status === 'recovered',
      icon: ShieldCheck,
      failed: false,
    },
    {
      key: 'revenue_recovered',
      title: 'Revenue Recovered',
      description: 'Revenue successfully restored',
      done: recoveryState.state === 'verified',
      icon: Coins,
      failed: false,
    },
  ]

  const handleCardKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      setIsModalOpen(true)
    }
  }

  return (
    <>
      <article
        className={`live-recovery-card ${recoveryState.state}`}
        role="button"
        tabIndex={0}
        onClick={() => setIsModalOpen(true)}
        onKeyDown={handleCardKeyDown}
        aria-label="Open recovery verification details"
      >
        <header className="live-recovery-header">
          <div>
            <span className="live-eyebrow">LIVE RAZORPAY TEST MODE</span>
            <h3>{recoveryState.title}</h3>
            <p className="live-subtitle">Real recovery execution through Razorpay Test Mode</p>
          </div>
          <span className={`status-badge ${recoveryState.badgeClass}`}>
            {recoveryState.state === 'verified' ? <CheckCircle2 size={14} /> : recoveryState.state === 'failed' ? <AlertTriangle size={14} /> : <Clock3 size={14} />}
            {recoveryState.badge}
          </span>
        </header>

        <div className="live-recovery-body">
          <div className="summary-card">
            <div className="summary-header">
              <span className="summary-transaction-id">{transaction?.transaction_id || 'TXN005'}</span>
              <strong className="summary-amount">₹{originalAmount.toLocaleString('en-IN')}</strong>
            </div>

            <div className="summary-meta-list">
              <div className="meta-row">
                <span>Customer</span>
                <strong>{transaction?.customer_name || 'Neha Sharma'}</strong>
              </div>
              <div className="meta-row">
                <span>Failure Reason</span>
                <strong>{transaction?.failure_reason || 'Bank Decline'}</strong>
              </div>
              <div className="meta-row">
                <span>Agent Decision</span>
                <strong>{toDisplayLabel(transaction?.recovery_action || 'Payment Link')}</strong>
              </div>
              <div className="meta-row">
                <span>Final Status</span>
                <strong>{toDisplayLabel(transaction?.status || transaction?.recovery_status || 'pending')}</strong>
              </div>
              <div className="meta-row">
                <span>Recovered Amount</span>
                <strong className={recoveryState.state === 'verified' ? 'accent-success' : ''}>₹{recoveredAmount.toLocaleString('en-IN')}</strong>
              </div>
            </div>
          </div>

          <div className="journey-card">
            <div className="journey-list">
              {stages.map((stage, index) => {
                const Icon = stage.icon
                const isDone = stage.done
                const isFailed = stage.failed

                return (
                  <div key={stage.key} className={`journey-step ${isDone ? 'done' : ''} ${isFailed ? 'failed' : ''}`}>
                    <div className="journey-trail">
                      <span className="journey-dot">{isDone ? <Check size={12} /> : isFailed ? <AlertTriangle size={12} /> : <span className="dot-faint" />}</span>
                      {index < stages.length - 1 && <span className="journey-line" />}
                    </div>

                    <div className="journey-content">
                      <div className="journey-head">
                        <span className="journey-icon"><Icon size={14} /></span>
                        <strong>{stage.title}</strong>
                      </div>
                      <small>{stage.description}</small>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        <div className={`recovered-strip ${recoveryState.state === 'verified' ? 'success' : 'pending'}`}>
          <div className="recovered-copy">
            <span>{recoveryState.state === 'verified' ? 'RECOVERED AMOUNT' : 'RECOVERY TARGET'}</span>
            <strong>₹{(recoveryState.state === 'verified' ? recoveredAmount : originalAmount).toLocaleString('en-IN')}</strong>
          </div>

          {recoveryState.state === 'verified' ? (
            <>
              <p>100% of this transaction recovered</p>
              <div className="recovery-progress-bar">
                <span style={{ width: `${recoveryProgress}%` }} />
              </div>
            </>
          ) : (
            <>
              <p>Current recovered amount: ₹{recoveredAmount.toLocaleString('en-IN')}</p>
              <div className="recovery-progress-bar">
                <span style={{ width: `${recoveryProgress}%` }} />
              </div>
            </>
          )}
        </div>

        <div className="live-audit-card">
          <div className="audit-header">
            <h4>Audit Timeline</h4>
          </div>

          {auditLogs.length ? (
            <div className="timeline-list">
              {auditLogs.map((entry, index) => {
                const action = String(entry?.action || '').trim() || 'Event'
                const reason = String(entry?.reason || '').trim() || 'No reason provided'
                const isLatest = latestSuccessfulEvent && (entry?.id === latestSuccessfulEvent?.id || entry?.created_at === latestSuccessfulEvent?.created_at)

                return (
                  <div key={`${action}-${entry?.created_at || index}`} className={`timeline-item ${isLatest ? 'latest' : ''}`}>
                    <div className="timeline-marker">
                      {isLatest ? <Check size={12} /> : <Activity size={12} />}
                    </div>
                    <div className="timeline-line" aria-hidden="true" />
                    <div className="timeline-content">
                      <div className="timeline-topline">
                        <strong>{toDisplayLabel(action)}</strong>
                        <time>{formatTimestamp(entry?.created_at)}</time>
                      </div>
                      <p>{reason}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="empty-timeline">
              <div className="empty-icon"><Clock3 size={20} /></div>
              <strong>Waiting for recovery events</strong>
              <p>Audit events will appear here as the recovery workflow progresses.</p>
            </div>
          )}
        </div>

        {recoveryState.state === 'verified' && (
          <div className="verification-strip">
            <span className="verified-mark">✓</span>
            <div>
              <strong>END-TO-END RECOVERY VERIFIED</strong>
              <small>Razorpay Test Payment • Signed Webhook • Database Updated • Audit Trail Recorded</small>
            </div>
          </div>
        )}
      </article>

      {isModalOpen && (
        <div className="live-recovery-modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="live-recovery-modal" role="dialog" aria-modal="true" aria-label="Recovery verification details" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header-row">
              <div>
                <span className="live-eyebrow">RECOVERY VERIFICATION</span>
                <h4>Recovery Verification Details</h4>
              </div>
              <button type="button" className="modal-close" aria-label="Close recovery verification" onClick={() => setIsModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="modal-grid">
              <div className="modal-stat">
                <span>Transaction</span>
                <strong>{transaction?.transaction_id || 'TXN005'}</strong>
              </div>
              <div className="modal-stat">
                <span>Payment Link ID</span>
                <strong>{transaction?.payment_link_id || 'Not generated'}</strong>
              </div>
              <div className="modal-stat">
                <span>Razorpay Reference ID</span>
                <strong>{transaction?.razorpay_reference_id || 'Not available'}</strong>
              </div>
              <div className="modal-stat">
                <span>Recovery Action</span>
                <strong>{toDisplayLabel(transaction?.recovery_action || 'Not recorded')}</strong>
              </div>
              <div className="modal-stat">
                <span>Failure Reason</span>
                <strong>{transaction?.failure_reason || 'Not available'}</strong>
              </div>
              <div className="modal-stat">
                <span>Original Amount</span>
                <strong>₹{originalAmount.toLocaleString('en-IN')}</strong>
              </div>
              <div className="modal-stat">
                <span>Recovered Amount</span>
                <strong>₹{recoveredAmount.toLocaleString('en-IN')}</strong>
              </div>
              <div className="modal-stat">
                <span>Recovery Status</span>
                <strong>{recoveryState.label}</strong>
              </div>
            </div>

            <div className="execution-trace">
              <h5>Execution Trace</h5>
              <div className="modal-timeline">
                {(auditLogs.length ? auditLogs : [{ action: 'Waiting for recovery events', reason: 'Audit events will appear here as the recovery workflow progresses.' }]).map((entry, index) => (
                  <div key={`${entry?.action || 'trace'}-${index}`} className="modal-timeline-item">
                    <div className="modal-timeline-marker">
                      {entry?.action ? <Check size={11} /> : <Clock3 size={11} />}
                    </div>
                    <div>
                      <strong>{toDisplayLabel(entry?.action || 'Waiting for recovery events')}</strong>
                      <p>{entry?.reason || 'Audit events will appear here as the recovery workflow progresses.'}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="verification-status-panel">
              <h5>Verification Status</h5>
              <ul className="verification-list">
                {verificationChecks.map((item) => (
                  <li key={item.label} className={item.ok ? 'verified' : 'muted'}>
                    <span>{item.ok ? '✓' : '•'}</span>
                    {item.label}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
