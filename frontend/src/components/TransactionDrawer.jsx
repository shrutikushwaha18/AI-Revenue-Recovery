import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

export default function TransactionDrawer({ row, onClose }) {
  const panelRef = useRef(null)

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        onClose()
      }

      if (event.key === 'Tab' && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
        const items = Array.from(focusable)
        if (!items.length) return
        const first = items[0]
        const last = items[items.length - 1]

        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  if (!row) return null

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside className="drawer-panel glass-modal" ref={panelRef} onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="Transaction details">
        <div className="drawer-header">
          <div>
            <span className="eyebrow">AI Explainability</span>
            <h3>{row.transaction_id}</h3>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="Close transaction modal">
            <X size={18} />
          </button>
        </div>

        <div className="drawer-grid">
          <div><span>Customer</span><strong>{row.customer_name || '—'}</strong></div>
          <div><span>Amount</span><strong>₹{Number(row.amount || 0).toLocaleString('en-IN')}</strong></div>
          <div><span>Failure Reason</span><strong>{row.failure_reason || '—'}</strong></div>
          <div><span>Retry Count</span><strong>{row.retry_count ?? 0}</strong></div>
          <div><span>Agent Decision</span><strong>{row.recovery_action || '—'}</strong></div>
          <div><span>Final Status</span><strong>{row.final_recovery_status || row.recovery_status || 'pending'}</strong></div>
          <div><span>Recovered Amount</span><strong>₹{Number(row.recovered_amount || 0).toLocaleString('en-IN')}</strong></div>
        </div>

        <div className="drawer-reason">
          <h4>Why this action?</h4>
          <p>{row.recovery_reason || 'No decision reason available.'}</p>
        </div>
      </aside>
    </div>
  )
}
