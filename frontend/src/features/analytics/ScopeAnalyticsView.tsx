import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { StatCard } from '../../components/ui/StatCard';
import { AccessibleChart } from '../../components/ui/AccessibleChart';
import { Skeleton } from '../../components/ui/Skeleton';
import { ErrorState } from '../../components/ui/ErrorState';
import { Button } from '../../components/ui/Button';

export const ScopeAnalyticsView: React.FC = () => {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const isExecutive = ['VICE_CHANCELLOR', 'REGISTRAR', 'CONTROLLER_OF_EXAMINATIONS'].includes(
    user?.role || ''
  );

  const defaultBreakdownBy = user?.role === 'DEAN' ? 'department' : 'course';
  const breakdownBy = searchParams.get('by') || defaultBreakdownBy;
  const trendMetric = searchParams.get('metric') || 'pass_rate';

  // 1. Fetch Overview KPIs
  const { data: overview, isLoading: loadingOverview, error: errorOverview } = useQuery({
    queryKey: ['analytics-overview', searchParams.toString()],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/analytics/overview/');
      if (error) throw error;
      return data;
    },
  });

  // 2. Fetch Performance Breakdown with Differential Privacy
  const { data: breakdownData, isLoading: loadingBreakdown } = useQuery({
    queryKey: ['analytics-breakdown', breakdownBy],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/analytics/breakdown/', {
        params: { query: { by: breakdownBy as 'department' | 'course' | 'teacher' } },
      });
      if (error) throw error;
      return data;
    },
  });

  // 3. Fetch Longitudinal Trend
  const { data: trendData, isLoading: loadingTrend } = useQuery({
    queryKey: ['analytics-trend', trendMetric],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/analytics/trend/', {
        params: { query: { metric: trendMetric as 'pass_rate' | 'average_score' | 'retention_rate' } },
      });
      if (error) throw error;
      return data;
    },
  });

  const handleBreakdownChange = (by: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('by', by);
    setSearchParams(next);
  };

  const handleTrendMetricChange = (metric: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('metric', metric);
    setSearchParams(next);
  };

  interface BreakdownChartItem {
    name: string;
    fullName: string;
    passRate: number;
    avgScore: number;
    studentCount: number;
  }

  const breakdownGroups = breakdownData?.groups || [];
  const chartBreakdown: BreakdownChartItem[] = breakdownGroups.map((g) => ({
    name: g.name.length > 20 ? `${g.name.substring(0, 18)}...` : g.name,
    fullName: g.name,
    passRate: g.pass_rate,
    avgScore: g.average_percentage,
    studentCount: g.student_count,
  }));

  const trendPoints = (trendData?.points || []).map((p) => ({
    semester: `Sem ${p.semester}`,
    value: p.value,
    sampleSize: p.sample_size,
  }));

  const breakdownColumns = [
    { key: 'name', header: 'Entity Name', render: (row: BreakdownChartItem) => row.fullName || row.name },
    { key: 'studentCount', header: 'Enrolled Count' },
    { key: 'passRate', header: 'Pass Rate (%)', render: (row: BreakdownChartItem) => `${row.passRate.toFixed(1)}%` },
    { key: 'avgScore', header: 'Average Score (%)', render: (row: BreakdownChartItem) => `${row.avgScore.toFixed(1)}%` },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Top Header with Scope Label */}
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-4)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700 }}>Institutional Academic Analytics</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>
            Aggregated performance insights for {user?.scope_label || 'University Scope'}
          </p>
        </div>
      </div>

      {/* KPI Overview Cards */}
      {loadingOverview ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
          <Skeleton height="7rem" />
          <Skeleton height="7rem" />
          <Skeleton height="7rem" />
          <Skeleton height="7rem" />
        </div>
      ) : errorOverview ? (
        <ErrorState title="Failed to load analytics overview" />
      ) : overview ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
          <StatCard
            label="Total Students"
            value={overview.total_students?.toLocaleString() ?? 0}
            subtitle={user?.scope_label}
            icon="👥"
          />
          <StatCard
            label="Overall Pass Rate"
            value={overview.pass_rate != null ? `${overview.pass_rate.toFixed(1)}%` : 'N/A'}
            subtitle="Passing standard >= 40%"
            icon="🎯"
          />
          <StatCard
            label="Average Score"
            value={overview.average_percentage != null ? `${overview.average_percentage.toFixed(1)}%` : 'N/A'}
            subtitle="Across all evaluations"
            icon="📊"
          />
          <StatCard
            label="At-Risk Rate"
            value={overview.at_risk_rate != null ? `${overview.at_risk_rate.toFixed(1)}%` : 'N/A'}
            subtitle={isExecutive ? 'Suppressed per privacy policy' : `${overview.at_risk_count ?? 0} total flagged students`}
            icon="⚠️"
          />
        </div>
      ) : null}

      {/* Breakdown Section with Differential Privacy */}
      <Card>
        <CardHeader
          title="Performance Breakdown & Comparison"
          subtitle="Differential privacy enabled (Cohorts < 10 students merged into 'Other')"
          action={
            <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
              {(user?.role === 'DEAN'
                ? ['department', 'course']
                : user?.role === 'HOD'
                ? ['course', 'batch', 'subject', 'teacher']
                : ['school', 'department']
              ).map((lvl) => (
                <Button
                  key={`lvl-${lvl}`}
                  variant={breakdownBy === lvl ? 'primary' : 'outline'}
                  size="sm"
                  onClick={() => handleBreakdownChange(lvl)}
                >
                  By {lvl.charAt(0).toUpperCase() + lvl.slice(1)}
                </Button>
              ))}
            </div>
          }
        />
        <CardBody>
          {loadingBreakdown ? (
            <Skeleton height="18rem" />
          ) : chartBreakdown.length === 0 ? (
            <p style={{ color: 'var(--color-text-muted)' }}>No breakdown data available for this scope.</p>
          ) : (
            <AccessibleChart
              title={`Pass Rate Breakdown by ${breakdownBy}`}
              description="Comparative pass rate and average percentage"
              tableColumns={breakdownColumns}
              tableData={chartBreakdown}
              keyExtractor={(item) => item.fullName}
            >
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={chartBreakdown} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" stroke="#9ca3af" interval={0} angle={-15} textAnchor="end" />
                  <YAxis domain={[0, 100]} stroke="#9ca3af" />
                  <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#f9fafb' }} />
                  <Bar dataKey="passRate" fill="#3b82f6" name="Pass Rate (%)" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="avgScore" fill="#10b981" name="Avg Score (%)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </AccessibleChart>
          )}
        </CardBody>
      </Card>

      {/* Longitudinal Performance Trend Section */}
      <Card>
        <CardHeader
          title="Longitudinal Performance Trends"
          subtitle="Semester-by-semester historical trajectory"
          action={
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              {[
                { label: 'Pass Rate', key: 'pass_rate' },
                { label: 'Average Score', key: 'avg_percentage' },
                { label: 'At-Risk Rate', key: 'at_risk_rate' },
              ].map((m) => (
                <Button
                  key={`metric-${m.key}`}
                  variant={trendMetric === m.key ? 'primary' : 'outline'}
                  size="sm"
                  onClick={() => handleTrendMetricChange(m.key)}
                >
                  {m.label}
                </Button>
              ))}
            </div>
          }
        />
        <CardBody>
          {loadingTrend ? (
            <Skeleton height="18rem" />
          ) : trendPoints.length === 0 ? (
            <p style={{ color: 'var(--color-text-muted)' }}>No historical trend data recorded yet.</p>
          ) : (
            <AccessibleChart
              title={`Trend Analysis: ${trendMetric}`}
              description="Longitudinal metrics across semesters"
              tableColumns={[
                { key: 'semester', header: 'Semester' },
                { key: 'value', header: 'Metric Value (%)' },
                { key: 'sampleSize', header: 'Sample Size (Students)' },
              ]}
              tableData={trendPoints}
              keyExtractor={(item) => item.semester}
            >
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={trendPoints} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="semester" stroke="#9ca3af" />
                  <YAxis domain={[0, 100]} stroke="#9ca3af" />
                  <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#f9fafb' }} />
                  <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={3} dot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            </AccessibleChart>
          )}
        </CardBody>
      </Card>
    </div>
  );
};
