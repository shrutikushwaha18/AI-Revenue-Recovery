import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'

const palette = ['#22c55e', '#f59e0b', '#ef4444', '#93c5fd', '#a78bfa']

export default function OutcomeBreakdownChart({ data = [] }) {
  const chartData = data.map((item, index) => ({ ...item, fill: palette[index % palette.length] }))

  return (
    <div className="chart-card pie-card">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={4}>
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
