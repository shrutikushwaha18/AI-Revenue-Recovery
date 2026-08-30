const controls = [
  'Maximum automatic retries: 2',
  'Payments above ₹10,000 require human review',
  'Unknown failures require manual review',
  'Recovered payments stop further recovery',
  'Customer opt-out stops automated communication',
  'Synthetic batch never creates real Razorpay links',
]

export default function SafetyPanel() {
  return (
    <section className="panel safety-panel">
      <div className="panel-header">
        <h3>Bounded Recovery Controls</h3>
      </div>

      <ul className="safety-list">
        {controls.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  )
}
