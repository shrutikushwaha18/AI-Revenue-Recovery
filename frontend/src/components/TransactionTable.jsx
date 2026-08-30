import { useMemo, useState } from 'react'

const PAGE_SIZE = 10

export default function TransactionTable({ transactions = [] }) {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [failureFilter, setFailureFilter] = useState('all')
  const [actionFilter, setActionFilter] = useState('all')
  const [page, setPage] = useState(1)

  const uniqueStatus = useMemo(() => [...new Set(transactions.map((trx) => trx.final_recovery_status || trx.recovery_status || 'pending'))], [transactions])
  const uniqueFailures = useMemo(() => [...new Set(transactions.map((trx) => trx.failure_reason || 'unknown'))], [transactions])
  const uniqueActions = useMemo(() => [...new Set(transactions.map((trx) => trx.recovery_action || 'none'))], [transactions])

  const filteredRows = useMemo(() => {
    const query = search.toLowerCase()
    return transactions.filter((trx) => {
      const matchesSearch = !query || [trx.transaction_id, trx.customer_name, trx.failure_reason, trx.recovery_action].join(' ').toLowerCase().includes(query)
      const matchesStatus = statusFilter === 'all' || (trx.final_recovery_status || trx.recovery_status || 'pending') === statusFilter
      const matchesFailure = failureFilter === 'all' || (trx.failure_reason || 'unknown') === failureFilter
      const matchesAction = actionFilter === 'all' || (trx.recovery_action || 'none') === actionFilter
      return matchesSearch && matchesStatus && matchesFailure && matchesAction
    })
  }, [transactions, search, statusFilter, failureFilter, actionFilter])

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const paginatedRows = filteredRows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  return (
    <section className="panel table-panel">
      <div className="panel-header section-header-row">
        <h3>Batch Recovery Transactions</h3>
      </div>

      <div className="filters">
        <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} placeholder="Search transaction or customer" />
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}>
          <option value="all">All statuses</option>
          {uniqueStatus.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
        <select value={failureFilter} onChange={(e) => { setFailureFilter(e.target.value); setPage(1) }}>
          <option value="all">All failure reasons</option>
          {uniqueFailures.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
        <select value={actionFilter} onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}>
          <option value="all">All actions</option>
          {uniqueActions.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Transaction ID</th>
              <th>Customer</th>
              <th>Amount</th>
              <th>Failure Reason</th>
              <th>Recovery Action</th>
              <th>Recovery Reason</th>
              <th>Retry Count</th>
              <th>Final Recovery Status</th>
              <th>Recovered Amount</th>
            </tr>
          </thead>
          <tbody>
            {paginatedRows.length ? paginatedRows.map((trx) => (
              <tr key={trx.transaction_id}>
                <td>{trx.transaction_id}</td>
                <td>{trx.customer_name || trx.customer || '—'}</td>
                <td>{`₹${Number(trx.amount || 0).toLocaleString('en-IN')}`}</td>
                <td>{trx.failure_reason || '—'}</td>
                <td>{trx.recovery_action || '—'}</td>
                <td>{trx.recovery_reason || '—'}</td>
                <td>{trx.retry_count ?? 0}</td>
                <td>{trx.final_recovery_status || trx.recovery_status || 'pending'}</td>
                <td>{`₹${Number(trx.recovered_amount || 0).toLocaleString('en-IN')}`}</td>
              </tr>
            )) : <tr><td colSpan="9">No records match the current filters.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <button disabled={currentPage === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</button>
        <span>Page {currentPage} of {totalPages}</span>
        <button disabled={currentPage === totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>Next</button>
      </div>
    </section>
  )
}
