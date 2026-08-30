export default function MetricCard({ title, value, detail, accent = 'teal' }) {
  return (
    <div className={`metric-card metric-${accent}`}>
      <div className="metric-label">{title}</div>
      <div className="metric-value">{value}</div>
      {detail ? <div className="metric-detail">{detail}</div> : null}
    </div>
  )
}
