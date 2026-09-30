import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { adminApi } from '../../../api/adminApi';
import { GlassCard } from '../../../components/ui/GlassCard';
import styles from './AnalyticsDashboard.module.css';

const ROUTE_COLORS: Record<string, string> = {
  vector:    'var(--chart-1)',
  graph:     'var(--chart-2)',
  hybrid:    'var(--chart-4)',
  cache_hit: 'var(--chart-3)',
};

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <GlassCard elevated className={styles.statCard}>
      <p className={styles.statLabel}>{label}</p>
      <p className={styles.statValue}>{value}</p>
      {sub && <p className={styles.statSub}>{sub}</p>}
    </GlassCard>
  );
}

export function AnalyticsDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-metrics'],
    queryFn: adminApi.getMetrics,
    refetchInterval: 30_000,
  });

  if (isLoading) return <div className={styles.loading}>Loading metrics…</div>;
  if (error || !data) return <div className={styles.error}>Failed to load metrics.</div>;

  const routeData = Object.entries(data.route_distribution).map(([name, value]) => ({
    name: name.replace('_', ' '),
    value,
    originalKey: name,
  }));

  const tokenData = [
    { name: 'Prompt', tokens: data.total_prompt_tokens },
    { name: 'Completion', tokens: data.total_completion_tokens },
  ];

  return (
    <div className={styles.dashboard}>
      <h2 className={styles.heading}>Analytics</h2>

      {/* Stat cards */}
      <div className={styles.stats}>
        <StatCard label="Total Queries" value={data.total_queries_processed.toLocaleString()} />
        <StatCard label="Total Tokens" value={data.total_tokens_used.toLocaleString()} />
        <StatCard label="Avg Latency" value={`${Number.isNaN(data.avg_latency_ms) || !data.avg_latency_ms ? 0 : Math.round(data.avg_latency_ms)}ms`} />
        <StatCard
          label="Cache Hit Rate"
          value={`${Number.isNaN(data.cache_hit_rate) || !data.cache_hit_rate ? 0 : (data.cache_hit_rate <= 1 ? data.cache_hit_rate * 100 : data.cache_hit_rate).toFixed(1)}%`}
          sub="Semantic cache"
        />
        <StatCard label="Active Users" value={data.active_users} />
      </div>

      {/* Charts row */}
      <div className={styles.charts}>
        {/* Route distribution donut */}
        <GlassCard className={styles.chartCard}>
          <p className={styles.chartTitle}>Route Distribution</p>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={routeData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={3}
              >
                {routeData.map((entry) => (
                  <Cell
                    key={entry.originalKey}
                    fill={ROUTE_COLORS[entry.originalKey] ?? 'var(--text-muted)'}
                  />
                ))}
              </Pie>
              <Legend
                wrapperStyle={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--chart-tooltip-bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-primary)',
                  fontSize: 'var(--text-xs)',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </GlassCard>

        {/* Token distribution bar */}
        <GlassCard className={styles.chartCard}>
          <p className={styles.chartTitle}>Token Distribution</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={tokenData} barSize={40}>
              <XAxis
                dataKey="name"
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--chart-tooltip-bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-primary)',
                  fontSize: 'var(--text-xs)',
                }}
                cursor={{ fill: 'var(--chart-grid)' }}
              />
              <Bar dataKey="tokens" radius={[6, 6, 0, 0]}>
                <Cell fill="var(--chart-1)" />
                <Cell fill="var(--chart-2)" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>
      </div>
    </div>
  );
}
