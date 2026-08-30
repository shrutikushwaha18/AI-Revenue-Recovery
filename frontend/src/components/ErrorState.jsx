export default function ErrorState({ message, onRetry }) {
  return (
    <div className="error-state">
      <h3>Unable to reach RecoverAI backend</h3>
      <p>{message || 'Please check the API connection and try again.'}</p>
      {onRetry ? (
        <button className="retry-button" onClick={onRetry} type="button">
          Retry
        </button>
      ) : null}
    </div>
  )
}
