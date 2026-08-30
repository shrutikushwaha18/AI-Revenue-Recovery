import { Activity, BadgeCheck, ShieldCheck } from 'lucide-react'

export default function HeroStatus() {
  return (
    <div className="hero-status-card">
      <div className="status-row">
        <span className="dot online" />
        <span>Agent Online</span>
      </div>
      <div className="status-row">
        <span className="dot cyan" />
        <span>Razorpay Test Mode</span>
      </div>
      <div className="status-row">
        <span className="dot amber" />
        <span>Policy Guard Active</span>
      </div>
      <div className="mini-health">
        <div className="health-header">
          <Activity size={14} />
          <span>System Health</span>
        </div>
        <div className="health-grid">
          <div><span>Agent Status</span><strong>Active</strong></div>
          <div><span>Payment API</span><strong>Connected</strong></div>
          <div><span>Webhook</span><strong>Verified</strong></div>
          <div><span>Batch Evaluated</span><strong>100 tx</strong></div>
        </div>
      </div>
      <div className="health-verified">
        <BadgeCheck size={16} />
        <span>Policy guard active</span>
      </div>
    </div>
  )
}
