import { ChevronDown, Download, ShieldCheck, Sparkles } from 'lucide-react'

export default function Header({
  statusChips = [],
  onChipClick,
  onExportMenuOpen,
  exportOpen,
  onExportCsv,
  onExportAudit,
  onStartDemo,
  onRunSimulation,
}) {
  return (
    <header className="topbar">
      <div className="brand-wrap">
        <div className="eyebrow-row">
          <Sparkles size={14} />
          <span>RecoverAI</span>
        </div>
        <div className="brand-lockup">
          <h1>RecoverAI</h1>
          <p className="subtitle">Autonomous Revenue Recovery Agent</p>
        </div>
      </div>

      <div className="topbar-tools">
        <div className="header-chip-row">
          {statusChips.map((chip) => (
            <button type="button" key={chip.label} className="status-chip" onClick={() => onChipClick?.(chip.label)}>
              {chip.label}
            </button>
          ))}
        </div>

        <div className="header-controls">
          <button type="button" className="secondary-button compact" onClick={onStartDemo}>Start Demo</button>
          <button type="button" className="primary-button compact" onClick={onRunSimulation}>Run Simulation</button>

          <div className="export-wrap">
            <button type="button" className="export-toggle" onClick={() => onExportMenuOpen?.((current) => !current)}>
              <Download size={14} />
              Export
              <ChevronDown size={14} />
            </button>

            {exportOpen && (
              <div className="export-menu">
                <button type="button" onClick={onExportCsv}>Export Batch CSV</button>
                <button type="button" onClick={onExportAudit}>Export Audit JSON</button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="brand-badge">
        <ShieldCheck size={18} />
        <span>Detect. Decide. Recover. Verify.</span>
      </div>
    </header>
  )
}
