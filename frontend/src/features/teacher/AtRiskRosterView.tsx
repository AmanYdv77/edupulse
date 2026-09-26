import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { DataTable } from '../../components/ui/DataTable';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { ErrorState } from '../../components/ui/ErrorState';

export const AtRiskRosterView: React.FC = () => {
  const { hasCapability } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const semesterFilter = searchParams.get('semester') ? Number(searchParams.get('semester')) : undefined;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['at-risk-roster', semesterFilter],
    queryFn: async () => {
      const { data: res, error: apiErr } = await apiClient.GET('/api/v1/analytics/at-risk/', {
        params: {
          query: {
            semester: semesterFilter,
          },
        },
      });
      if (apiErr) throw apiErr;
      return res || [];
    },
  });

  const handleSemesterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    const next = new URLSearchParams(searchParams);
    if (val) next.set('semester', val);
    else next.delete('semester');
    setSearchParams(next);
  };

  const handleExportCsv = () => {
    const params = new URLSearchParams();
    if (semesterFilter) params.set('semester', String(semesterFilter));
    window.location.href = `/api/v1/analytics/export/at-risk.csv?${params.toString()}`;
  };

  interface AtRiskStudentItem {
    id: number;
    roll_no: string;
    name: string;
    course_code: string;
    batch_code: string;
    semester: number;
    predicted_percentage?: number | null;
    risk_band?: 'low' | 'medium' | 'high' | 'insufficient_data';
    reasons?: Array<string | { feature: string; impact?: string }>;
  }

  const students = (Array.isArray(data) ? data : []) as unknown as AtRiskStudentItem[];
  const totalCount = students.length;

  const columns = [
    { key: 'roll_no', header: 'Roll Number' },
    { key: 'name', header: 'Student Name' },
    { key: 'course_code', header: 'Course' },
    { key: 'batch_code', header: 'Batch' },
    { key: 'semester', header: 'Semester' },
    {
      key: 'predicted_percentage',
      header: 'Forecast Score',
      render: (row: AtRiskStudentItem) =>
        row.predicted_percentage !== null && row.predicted_percentage !== undefined
          ? `${row.predicted_percentage.toFixed(1)}%`
          : 'N/A',
    },
    {
      key: 'risk_band',
      header: 'Risk Level',
      render: (row: AtRiskStudentItem) => <Badge riskBand={row.risk_band} />,
    },
    {
      key: 'reasons',
      header: 'Contributing Drivers',
      render: (row: AtRiskStudentItem) => {
        const rList = Array.isArray(row.reasons) ? row.reasons : [];
        if (rList.length === 0) return <span style={{ color: 'var(--color-text-dim)' }}>-</span>;
        return (
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
            {rList
              .slice(0, 2)
              .map((r) => (typeof r === 'string' ? r : `${r.feature}`))
              .join('; ')}
          </span>
        );
      },
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-4)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700 }}>Early Warning & At-Risk Roster</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>
            Students flagged by ML prediction models requiring academic advisory or intervention
          </p>
        </div>

        {(hasCapability('export_at_risk_roster') ||
          hasCapability('export_class_roster') ||
          hasCapability('export_department_roster') ||
          hasCapability('export_school_roster')) && (
          <Button variant="outline" size="sm" onClick={handleExportCsv} leftIcon="📥">
            Export CSV
          </Button>
        )}
      </div>

      <Card>
        <CardHeader
          title={`At-Risk Students (${totalCount} Total)`}
          action={
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <label htmlFor="semester-filter-select" style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
                Filter Semester:
              </label>
              <select
                id="semester-filter-select"
                value={semesterFilter || ''}
                onChange={handleSemesterChange}
                style={{ padding: '0.2rem 0.5rem', width: 'auto' }}
              >
                <option value="">All Semesters</option>
                <option value="1">Semester 1</option>
                <option value="2">Semester 2</option>
                <option value="3">Semester 3</option>
                <option value="4">Semester 4</option>
              </select>
            </div>
          }
        />
        <CardBody>
          {isLoading ? (
            <Skeleton height="15rem" />
          ) : error ? (
            <ErrorState title="Failed to load at-risk roster" onRetry={() => refetch()} />
          ) : (
            <DataTable
              columns={columns}
              data={students}
              keyExtractor={(item) => item.roll_no || item.id}
              emptyMessage="No students currently flagged in high-risk band for the selected filters."
            />
          )}
        </CardBody>
      </Card>
    </div>
  );
};
