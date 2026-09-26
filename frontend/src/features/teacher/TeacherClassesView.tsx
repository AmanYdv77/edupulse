import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { apiClient } from '../../api/client';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { StatCard } from '../../components/ui/StatCard';
import { AccessibleChart } from '../../components/ui/AccessibleChart';
import { Skeleton } from '../../components/ui/Skeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import { Button } from '../../components/ui/Button';

export const TeacherClassesView: React.FC = () => {
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(null);

  // 1. Fetch Teacher Assignments
  const { data: assignments, isLoading: loadingAssignments } = useQuery({
    queryKey: ['teaching-assignments'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/teaching-assignments/');
      if (error) throw error;
      return data || [];
    },
  });

  const activeAssignment = assignments?.find((a) => a.id === selectedAssignmentId) || assignments?.[0];
  const subjectId = activeAssignment?.subject_id;

  // 2. Fetch Scope Overview KPIs
  const { data: overview } = useQuery({
    queryKey: ['analytics-overview', activeAssignment?.batch_id],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/analytics/overview/', {
        params: { query: { batch: activeAssignment?.batch_id } },
      });
      if (error) throw error;
      return data;
    },
    enabled: !!activeAssignment,
  });

  // 3. Fetch Score Distribution for Active Subject
  const { data: distData, isLoading: loadingDist } = useQuery({
    queryKey: ['analytics-distribution', subjectId, activeAssignment?.batch_id],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/analytics/distribution/', {
        params: { query: { subject: subjectId!, batch: activeAssignment?.batch_id } },
      });
      if (error) throw error;
      return data;
    },
    enabled: !!subjectId,
  });

  if (loadingAssignments) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        <Skeleton height="3rem" />
        <Skeleton height="8rem" />
        <Skeleton height="15rem" />
      </div>
    );
  }

  if (!assignments || assignments.length === 0) {
    return <EmptyState title="No teaching assignments found" description="You have not been assigned to any course batches this term." />;
  }

  const histogramData = distData?.bins?.map((b) => ({
    range: b.label,
    count: b.count,
  })) || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700 }}>My Assigned Classes & Performance</h1>
        <p style={{ color: 'var(--color-text-muted)' }}>
          Scoped academic metrics and grade distribution for your assigned sections
        </p>
      </div>

      {/* Assignment Switcher Tabs */}
      <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
        {assignments.map((a) => {
          const isSelected = (activeAssignment?.id === a.id);
          return (
            <Button
              key={`assign-${a.id}`}
              variant={isSelected ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setSelectedAssignmentId(a.id)}
            >
              {a.subject_code} - {a.batch_name}
            </Button>
          );
        })}
      </div>

      {/* Class Overview Stats */}
      {overview && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
          <StatCard
            label="Total Students"
            value={overview.total_students}
            subtitle={activeAssignment?.batch_name}
            icon="👥"
          />
          <StatCard
            label="Pass Rate"
            value={`${overview.pass_rate.toFixed(1)}%`}
            subtitle="Passing standard >= 40%"
            icon="🎯"
          />
          <StatCard
            label="Average Score"
            value={`${overview.average_percentage.toFixed(1)}%`}
            subtitle="Section average"
            icon="📊"
          />
          <StatCard
            label="At-Risk Count"
            value={overview.at_risk_count}
            subtitle={`${overview.at_risk_rate.toFixed(1)}% of section`}
            icon="⚠️"
          />
        </div>
      )}

      {/* Score Distribution Histogram */}
      <Card>
        <CardHeader
          title={`Score Distribution: ${activeAssignment?.subject_name} (${activeAssignment?.subject_code})`}
          subtitle={`Total Records: ${distData?.total_records || 0} students`}
        />
        <CardBody>
          {loadingDist ? (
            <Skeleton height="15rem" />
          ) : histogramData.length === 0 ? (
            <EmptyState title="No marks distribution data" description="No results recorded for this subject." />
          ) : (
            <AccessibleChart
              title="Percentage Score Distribution"
              description="Histogram of student scores across standard percentage brackets"
              tableColumns={[
                { key: 'range', header: 'Score Range' },
                { key: 'count', header: 'Student Count' },
              ]}
              tableData={histogramData}
              keyExtractor={(item) => item.range}
            >
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={histogramData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="range" stroke="#9ca3af" />
                  <YAxis stroke="#9ca3af" allowDecimals={false} />
                  <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#f9fafb' }} />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </AccessibleChart>
          )}
        </CardBody>
      </Card>
    </div>
  );
};
