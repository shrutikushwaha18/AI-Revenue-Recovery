import { BarChart, Bar, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from 'recharts'

const palette = ['#22c55e', '#f59e0b', '#ef4444', '#60a5fa', '#a78bfa']

export default function OutcomeBreakdownChart({ data = [] }) {
  const chartData = data.map((item, index) => ({ ...item, fill: palette[index % palette.length] }))

  return (
    <div className="chart-card bar-card">
      <ResponsiveContainer width="100%" height={380}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 14 }}>
          <XAxis type="number" allowDecimals={false} />
          <YAxis type="category" dataKey="name" width={100} />
          <Tooltip />
          <Bar dataKey="value" radius={[0, 8, 8, 0]}>
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
