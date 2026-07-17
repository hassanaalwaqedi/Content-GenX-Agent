import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const COLORS = ['#4f8cff', '#21c7e8', '#2dd4a4', '#9b6dff', '#f5a623', '#ef6b7b'];

const tooltipStyle = {
  background: '#101a2d', border: '1px solid rgba(120,150,210,.22)', borderRadius: 8, color: '#f4f7ff', fontSize: 12,
};

export function TrendDistributionPanel({ data }) {
  return (
    <section className="dash-panel dash-chart-panel">
      <div className="dash-panel-heading"><h2><span aria-hidden="true">▥</span> Trend Distribution</h2></div>
      {data.length > 0 ? (
        <div className="dash-bar-chart">
          <ResponsiveContainer width="100%" height={170}>
            <BarChart data={data.slice(0, 5)} layout="vertical" margin={{ top: 1, right: 24, bottom: 0, left: 2 }} barSize={16}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" width={106} tick={{ fill: '#91a0be', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} labelFormatter={(value, payload) => payload?.[0]?.payload?.fullName || value} />
              <Bar dataKey="videos" fill="#4f8cff" radius={[3, 3, 3, 3]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : <div className="dash-chart-empty">No trend distribution yet</div>}
    </section>
  );
}

export function NicheDistributionPanel({ data }) {
  const total = data.reduce((sum, item) => sum + item.videos, 0) || 1;
  return (
    <section className="dash-panel dash-chart-panel dash-niche-panel">
      <div className="dash-panel-heading"><h2><span aria-hidden="true">◉</span> Niche Distribution</h2></div>
      {data.length > 0 ? (
        <div className="dash-niche-body">
          <ResponsiveContainer width="48%" height={164}>
            <PieChart>
              <Pie data={data} dataKey="videos" nameKey="fullName" cx="50%" cy="50%" innerRadius={42} outerRadius={66} paddingAngle={3} stroke="none">
                {data.map((item, index) => <Cell key={item.fullName} fill={COLORS[index % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
          <div className="dash-niche-legend">
            {data.slice(0, 4).map((item, index) => (
              <div key={item.fullName}>
                <span style={{ background: COLORS[index % COLORS.length] }} />
                <label title={item.fullName}>{item.name}</label>
                <strong>{Math.round((item.videos / total) * 100)}%</strong>
              </div>
            ))}
          </div>
        </div>
      ) : <div className="dash-chart-empty">No niche distribution yet</div>}
    </section>
  );
}
