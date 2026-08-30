export default function ErrorState({ message }) {
  return (
    <div className="error-state">
      <h3>Unable to load dashboard data</h3>
      <p>{message || 'Please check the API connection and try again.'}</p>
    </div>
  )
}
