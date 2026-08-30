import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

const palette = ['#f59e0b', '#38bdf8', '#a78bfa', '#34d399', '#f87171']

export default function RecoveryBreakdownChart({ data = [], total = 0 }) {
  const chartData = data.map((item, index) => ({ ...item, fill: palette[index % palette.length] }))

  return (
    <div className="chart-card donut-card">
      <ResponsiveContainer width="100%" height={380}>
        <PieChart>
          <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={88} paddingAngle={3}>
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
      <div className="donut-center">
        <strong>{total}</strong>
        <span>Decisions</span>
      </div>
    </div>
  )
}
