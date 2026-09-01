import { Check, Circle, ShieldCheck } from 'lucide-react'

const stages = [
  { key: 'observe', label: 'OBSERVE', detail: 'Transaction state loaded' },
  { key: 'reason', label: 'REASON', detail: 'Recovery decision made' },
  { key: 'guard', label: 'POLICY GUARD', detail: 'Execution policy evaluated' },
  { key: 'act', label: 'ACT', detail: 'Razorpay action executed' },
  { key: 'verify', label: 'VERIFY', detail: 'Signed webhook confirmed outcome' },
]

const formatAmount = (value) => `₹${Number(value || 0).toLocaleString('en-IN')}`

export default function AgentDecisionTrace({ trace, transaction, loading = false, error = false }) {
  if (loading) {
    return (
      <section className="agent-trace-panel panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">AI AGENT DECISION TRACE</span>
            <h3>Loading agent reasoning...</h3>
          </div>
        </div>
      </section>
    )
  }

  if (error || !trace) {
    return (
      <section className="agent-trace-panel panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">AI AGENT DECISION TRACE</span>
            <h3>Agent trace unavailable</h3>
          </div>
        </div>
      </section>
    )
  }

  const guardrails = trace?.guardrails || []
  const guardrailsPassed = guardrails.filter((check) => check.name !== 'execution_allowed').every((check) => check.passed)
  const decision = trace?.decision
  const hasDecision = Boolean(decision?.action)
  const stagesComplete = [
    Boolean(trace?.observation),
    Boolean(trace?.decision?.action),
    guardrailsPassed,
    Boolean(trace?.execution?.executed),
    Boolean(trace?.outcome?.signed_webhook && trace?.outcome?.recovered),
  ]
  const reasoningSourceLabel = decision?.reasoning_source === 'llm' ? 'LLM' : 'Safe deterministic fallback'
  const recommendedActionLabel = decision?.recommended_action?.replace(/_/g, ' ') || decision?.action?.replace(/_/g, ' ') || 'Unavailable'
  const finalGuardedActionLabel = decision?.final_guarded_action?.replace(/_/g, ' ') || decision?.action?.replace(/_/g, ' ') || 'Unavailable'
  const confidenceLabel = decision?.reasoning_source === 'llm'
    ? 'LLM recommendation — not a probability'
    : (typeof decision?.confidence === 'number' ? `${Math.round(decision.confidence * 100)}%` : 'Unavailable')

  return (
    <section className="agent-trace-panel panel">
      <div className="panel-header trace-header">
        <div>
          <span className="eyebrow">AI AGENT DECISION TRACE</span>
          <h3>Autonomous recovery trace</h3>
          <p>Razorpay Test Mode • {transaction?.transaction_id || trace?.transaction_id}</p>
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
          <span>OBSERVE</span>
          <strong>{trace?.observation?.transaction_id || transaction?.transaction_id || 'Unavailable'}</strong>
          <small>{formatAmount(trace?.observation?.amount)} • {trace?.observation?.failure_reason?.replace(/_/g, ' ') || 'Unknown failure'} • {trace?.observation?.retry_count || 0} retries • {trace?.observation?.status || 'Unavailable'}</small>
        </div>
        <div className="trace-detail-block">
          <span>DECISION</span>
          {hasDecision ? (
            <>
              <strong>AI Reasoner</strong>
              <small>Recommended Action: {recommendedActionLabel}</small>
              <small>Reasoning Source: {reasoningSourceLabel}</small>
              <small>Risk Level: {decision?.risk_level || 'Unavailable'}</small>
              <small>Human Review: {decision?.requires_human_review ? 'Required' : 'Not Required'}</small>
              <small>Confidence: {confidenceLabel}</small>
              <small>Confidence Type: {decision?.confidence_type || 'Unavailable'}</small>
              <small>Reason: {decision?.reason || 'Unavailable'}</small>
            </>
          ) : (
            <strong>Decision data unavailable</strong>
          )}
        </div>
        <div className="trace-detail-block">
          <span>POLICY GUARD</span>
          {decision?.policy_override === true ? (
            <>
              <strong>POLICY OVERRIDE</strong>
              <small>LLM Recommendation: {recommendedActionLabel.charAt(0).toUpperCase() + recommendedActionLabel.slice(1)}</small>
              <small>Final Guarded Action: {finalGuardedActionLabel.charAt(0).toUpperCase() + finalGuardedActionLabel.slice(1)}</small>
              <small>Reason: {decision?.policy_override_reason || 'Unavailable'}</small>
              <small>{decision?.guarded_reason || 'Unavailable'}</small>
            </>
          ) : (
            <>
              <strong>{guardrailsPassed ? 'Policy checks passed' : 'Execution blocked by policy'}</strong>
              <small>{guardrails.filter((check) => check.passed).length}/{guardrails.length} checks passed</small>
              <small>LLM recommendation approved by policy guard</small>
            </>
          )}
          <div className="trace-guardrail-list">
            {guardrails.map((check) => (
              <small key={check.name}>{check.passed ? 'PASSED' : 'BLOCKED'}: {check.name} • {check.reason}</small>
            ))}
          </div>
        </div>
        <div className="trace-detail-block">
          <span>ACT</span>
          <strong>{trace?.execution?.executed ? 'Executed' : 'Awaiting execution / recovery outcome'}</strong>
          <small>Action: {decision?.final_guarded_action || trace?.execution?.action || 'Unavailable'}</small>
          <small>Tool: {trace?.execution?.external_tool || 'No external action'}</small>
          <small>Payment Link Created: {trace?.execution?.payment_link_created ? 'Yes' : 'No'}</small>
        </div>
        <div className="trace-detail-block">
          <span>VERIFY</span>
          <strong>{trace?.outcome?.recovered ? `${formatAmount(trace?.outcome?.recovered_amount)} recovered` : 'Awaiting execution / recovery outcome'}</strong>
          <small>Status: {trace?.outcome?.status || 'Unavailable'} • Recovered: {trace?.outcome?.recovered ? 'Yes' : 'No'}</small>
          <small>Signed Webhook: {trace?.outcome?.signed_webhook ? 'Yes' : 'No'}</small>
        </div>
      </div>
    </section>
  )
}
