export default function AuditTimeline({ auditLogs = [] }) {
  return (
    <div className="timeline">
      {auditLogs.length ? auditLogs.map((event, index) => (
        <div key={`${event.action}-${index}`} className="timeline-item">
          <div className="timeline-dot" />
          <div>
            <strong>{event.action}</strong>
            <p>{event.reason}</p>
          </div>
        </div>
      )) : <p>No audit entries available.</p>}
    </div>
  )
}
