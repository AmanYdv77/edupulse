import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { StatCard } from '../../components/ui/StatCard';
import { DataTable } from '../../components/ui/DataTable';
import { AccessibleChart } from '../../components/ui/AccessibleChart';
import { Skeleton } from '../../components/ui/Skeleton';
import { ErrorState } from '../../components/ui/ErrorState';
import { EmptyState } from '../../components/ui/EmptyState';
import { Button } from '../../components/ui/Button';

export const StudentResults: React.FC = () => {
  const { user } = useAuth();
  const studentId = user?.id || 0;
  const [selectedSemester, setSelectedSemester] = useState<number | null>(null);

  const {
    data: resultsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['student-results', studentId],
    queryFn: async () => {
      const { data, error: apiErr } = await apiClient.GET('/api/v1/students/{id}/results/', {
        params: { path: { id: studentId } },
      });
      if (apiErr) throw apiErr;
      return data;
    },
    enabled: studentId > 0,
  });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        <Skeleton height="3rem" />
        <Skeleton height="6rem" />
        <Skeleton height="15rem" />
      </div>
    );
  }

  if (error) {
    return <ErrorState title="Failed to load academic results" onRetry={() => refetch()} />;
  }

  if (!resultsData || !resultsData.semester_results || resultsData.semester_results.length === 0) {
    return <EmptyState title="No results available" description="Official academic results have not been published yet." />;
  }

  const semesterResults = resultsData.semester_results;
  const allSubjectResults = resultsData.subject_results || [];

  const activeSem = selectedSemester || semesterResults[0]?.semester || 1;
  const activeSemResult = semesterResults.find((s) => s.semester === activeSem);
  const activeSubjects = allSubjectResults.filter((sub) => sub.semester === activeSem);

  const trendData = semesterResults
    .map((s) => ({
      semester: `Sem ${s.semester}`,
      sgpa: s.sgpa || 0,
      percentage: s.percentage || 0,
    }))
    .sort((a, b) => a.semester.localeCompare(b.semester));

  interface SubjectRow {
    subject_code: string;
    subject_name: string;
    subject_credits?: number;
    internal_marks?: number | null;
    total_secured?: number | null;
    max_marks?: number | null;
    grade?: string | null;
  }

  const columns = [
    { key: 'subject_code', header: 'Subject Code' },
    { key: 'subject_name', header: 'Subject Title' },
    { key: 'subject_credits', header: 'Credits' },
    { key: 'internal_marks', header: 'Internal Marks', render: (row: SubjectRow) => row.internal_marks ?? '-' },
    { key: 'total_secured', header: 'Total Score', render: (row: SubjectRow) => `${row.total_secured ?? '-'} / ${row.max_marks ?? 100}` },
    { key: 'grade', header: 'Grade', render: (row: SubjectRow) => <strong>{row.grade || '-'}</strong> },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700 }}>Academic Performance Records</h1>
        <p style={{ color: 'var(--color-text-muted)' }}>
          Official semester grades, marks, and SGPA progression
        </p>
      </div>

      {/* Semester Selection Tabs */}
      <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
        {semesterResults.map((s) => (
          <Button
            key={`tab-sem-${s.semester}`}
            variant={s.semester === activeSem ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setSelectedSemester(s.semester)}
          >
            Semester {s.semester}
          </Button>
        ))}
      </div>

      {/* Active Semester Summary Stats */}
      {activeSemResult && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
          <StatCard
            label="Semester SGPA"
            value={activeSemResult.sgpa !== undefined ? activeSemResult.sgpa.toFixed(2) : 'N/A'}
            subtitle={`Semester ${activeSem}`}
            icon="🎓"
          />
          <StatCard
            label="Percentage"
            value={activeSemResult.percentage !== undefined ? `${activeSemResult.percentage.toFixed(1)}%` : 'N/A'}
            subtitle="Weighted aggregate"
            icon="📊"
          />
          <StatCard
            label="Recorded Attendance"
            value={activeSemResult.attendance_percentage !== null && activeSemResult.attendance_percentage !== undefined ? `${activeSemResult.attendance_percentage.toFixed(1)}%` : 'Unrecorded'}
            subtitle="Official institutional records"
            icon="⏱️"
          />
          <StatCard
            label="Total Credits"
            value={activeSemResult.total_credits || 0}
            subtitle="Earned credits"
            icon="📝"
          />
        </div>
      )}

      {/* Subject Marks Table */}
      <Card>
        <CardHeader
          title={`Semester ${activeSem} Subject Marks`}
          subtitle={`${activeSubjects.length} Registered Subjects`}
        />
        <CardBody>
          <DataTable
            columns={columns}
            data={activeSubjects}
            keyExtractor={(item) => item.id}
            emptyMessage="No subject marks recorded for this semester."
          />
        </CardBody>
      </Card>

      {/* Longitudinal SGPA Trend */}
      {trendData.length > 1 && (
        <Card>
          <CardHeader title="Longitudinal SGPA Trajectory" subtitle="Semester-by-semester grade point average progression" />
          <CardBody>
            <AccessibleChart
              title="SGPA Trajectory"
              description="Historical SGPA per semester"
              tableColumns={[
                { key: 'semester', header: 'Semester' },
                { key: 'sgpa', header: 'SGPA' },
                { key: 'percentage', header: 'Percentage' },
              ]}
              tableData={trendData}
              keyExtractor={(item) => item.semester}
            >
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={trendData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="semester" stroke="#9ca3af" />
                  <YAxis domain={[0, 10]} stroke="#9ca3af" />
                  <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#f9fafb' }} />
                  <Line type="monotone" dataKey="sgpa" stroke="#3b82f6" strokeWidth={3} dot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            </AccessibleChart>
          </CardBody>
        </Card>
      )}
    </div>
  );
};
