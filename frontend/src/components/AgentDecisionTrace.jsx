import { Check, Circle, ShieldCheck } from 'lucide-react'

const stages = [
  { key: 'observe', label: 'OBSERVE', detail: 'Transaction state loaded' },
  { key: 'reason', label: 'REASON', detail: 'Recovery decision made' },
  { key: 'guard', label: 'POLICY GUARD', detail: 'Execution policy evaluated' },
  { key: 'act', label: 'ACT', detail: 'Razorpay action executed' },
  { key: 'verify', label: 'VERIFY', detail: 'Signed webhook confirmed outcome' },
]

const formatAmount = (value) => `₹${Number(value || 0).toLocaleString('en-IN')}`

export default function AgentDecisionTrace({ trace }) {
  if (!trace) {
    return (
      <section className="agent-trace-panel panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">AI AGENT DECISION TRACE</span>
            <h3>Waiting for verified live recovery</h3>
          </div>
        </div>
      </section>
    )
  }

  const guardrailsPassed = trace.guardrails?.filter((check) => check.name !== 'execution_allowed').every((check) => check.passed)
  const stagesComplete = [
    Boolean(trace.observation),
    Boolean(trace.decision?.action),
    guardrailsPassed,
    Boolean(trace.execution?.executed),
    Boolean(trace.outcome?.signed_webhook && trace.outcome?.recovered),
  ]

  return (
    <section className="agent-trace-panel panel">
      <div className="panel-header trace-header">
        <div>
          <span className="eyebrow">AI AGENT DECISION TRACE</span>
          <h3>Autonomous recovery trace</h3>
          <p>Razorpay Test Mode • {trace.transaction_id}</p>
        </div>
        <ShieldCheck size={22} className="trace-shield" />
      </div>

      <div className="trace-steps">
        {stages.map((stage, index) => (
          <div className="trace-step-wrap" key={stage.key}>
            <div className={`trace-step ${stagesComplete[index] ? 'complete' : ''}`}>
              <span className="trace-step-icon">{stagesComplete[index] ? <Check size={15} /> : <Circle size={12} />}</span>
              <div>
                <strong>{stage.label}</strong>
                <small>{stage.detail}</small>
              </div>
            </div>
            {index < stages.length - 1 && <span className={`trace-connector ${stagesComplete[index] ? 'complete' : ''}`} aria-hidden="true" />}
          </div>
        ))}
      </div>

      <div className="trace-details">
        <div className="trace-detail-block">
          <span>OBSERVATION</span>
          <strong>{trace.observation.failure_reason?.replace(/_/g, ' ') || 'Unknown failure'}</strong>
          <small>{formatAmount(trace.observation.amount)} at risk • {trace.observation.retry_count || 0} retries</small>
        </div>
        <div className="trace-detail-block">
          <span>DECISION</span>
          <strong>{trace.decision.action?.replace(/_/g, ' ')}</strong>
          <small>{trace.decision.reason}</small>
        </div>
        <div className="trace-detail-block">
          <span>POLICY GUARD</span>
          <strong>{guardrailsPassed ? 'Policy checks passed' : 'Execution blocked by policy'}</strong>
          <small>{trace.guardrails?.filter((check) => check.passed).length || 0}/{trace.guardrails?.length || 0} checks passed</small>
        </div>
        <div className="trace-detail-block">
          <span>OUTCOME</span>
          <strong>{formatAmount(trace.outcome.recovered_amount)} recovered</strong>
          <small>{trace.outcome.signed_webhook ? 'Signed webhook' : 'Awaiting signed webhook'}</small>
        </div>
      </div>
    </section>
  )
}
