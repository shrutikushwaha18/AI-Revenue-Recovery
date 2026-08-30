export default function LoadingState({ message = 'Loading dashboard data...' }) {
  return (
    <div className="loading-state">
      <div className="spinner" aria-label="Loading" />
      <p>{message}</p>
    </div>
  )
}
