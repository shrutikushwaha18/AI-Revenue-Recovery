export const formatCurrency = (value) => {
  const numeric = Number(value || 0)
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(numeric)
}

export const formatPercent = (value) => {
  const numeric = Number(value || 0)
  return `${numeric.toFixed(1)}%`
}

export const formatStatus = (value) => {
  if (!value) return '—'
  return String(value).replace(/_/g, ' ')
}
