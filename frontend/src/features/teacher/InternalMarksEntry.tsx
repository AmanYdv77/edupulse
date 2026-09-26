import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient, refreshCsrf } from '../../api/client';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { EmptyState } from '../../components/ui/EmptyState';

interface MarkRow {
  studentId: string;
  marks: string;
}

export const InternalMarksEntry: React.FC = () => {
  interface MarkErrorItem {
    student_id?: number;
    error: string;
  }

  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | ''>('');
  const [rows, setRows] = useState<MarkRow[]>([
    { studentId: '', marks: '' },
    { studentId: '', marks: '' },
    { studentId: '', marks: '' },
  ]);
  const [formError, setFormError] = useState<string | null>(null);
  const [resultMessage, setResultMessage] = useState<{ updated: number; errors: Array<MarkErrorItem | string> } | null>(null);

  const { data: assignments, isLoading } = useQuery({
    queryKey: ['teaching-assignments'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/teaching-assignments/');
      if (error) throw error;
      return data || [];
    },
  });

  const activeAssignment = assignments?.find((a) => a.id === Number(selectedAssignmentId));

  const saveMarksMutation = useMutation({
    mutationFn: async (payload: {
      subject_id: number;
      batch_id: number;
      semester: number;
      marks: Array<{ student_id: number; internal_marks: string }>;
    }) => {
      await refreshCsrf();
      const { data, error: apiErr } = await apiClient.POST('/api/v1/internal-marks/', {
        body: payload,
      });
      if (apiErr) throw apiErr;
      return data;
    },
    onSuccess: (data: unknown) => {
      const resp = data as { updated_count?: number; errors?: Array<MarkErrorItem | string> } | undefined;
      const updatedCount = resp?.updated_count ?? rows.filter((r) => r.studentId && r.marks).length;
      const errors = resp?.errors ?? [];
      setResultMessage({ updated: updatedCount, errors });
      setFormError(null);
    },
    onError: (err: unknown) => {
      const msg =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : err instanceof Error
            ? err.message
            : 'Failed to update internal marks.';
      setFormError(msg);
    },
  });

  const handleAddRow = () => {
    setRows([...rows, { studentId: '', marks: '' }]);
  };

  const handleRowChange = (index: number, field: 'studentId' | 'marks', value: string) => {
    const next = [...rows];
    next[index][field] = value;
    setRows(next);
  };

  const handleRemoveRow = (index: number) => {
    if (rows.length <= 1) return;
    setRows(rows.filter((_, idx) => idx !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setResultMessage(null);

    if (!activeAssignment) {
      setFormError('Please select a teaching assignment.');
      return;
    }

    const validEntries = rows.filter((r) => r.studentId.trim() !== '' && r.marks.trim() !== '');
    if (validEntries.length === 0) {
      setFormError('Please enter at least one student mark.');
      return;
    }

    const maxMarks = activeAssignment.internal_max || 100;
    const formattedMarks = [];

    for (const entry of validEntries) {
      const sId = Number(entry.studentId);
      const mVal = Number(entry.marks);

      if (isNaN(sId) || sId <= 0) {
        setFormError(`Invalid Student ID: ${entry.studentId}`);
        return;
      }
      if (isNaN(mVal) || mVal < 0 || mVal > maxMarks) {
        setFormError(`Marks for student ${entry.studentId} must be between 0 and ${maxMarks}.`);
        return;
      }

      formattedMarks.push({
        student_id: sId,
        internal_marks: String(mVal),
      });
    }

    saveMarksMutation.mutate({
      subject_id: activeAssignment.subject_id,
      batch_id: activeAssignment.batch_id,
      semester: activeAssignment.semester,
      marks: formattedMarks,
    });
  };

  if (isLoading) {
    return <Skeleton height="20rem" />;
  }

  if (!assignments || assignments.length === 0) {
    return <EmptyState title="No teaching assignments" description="You must be assigned to a section to enter internal marks." />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700 }}>Internal Marks Assessment Entry</h1>
        <p style={{ color: 'var(--color-text-muted)' }}>
          Record continuous evaluation and internal assessment scores for your class rosters
        </p>
      </div>

      <Card>
        <CardHeader title="Batch Marks Assessment" subtitle="Select assigned course section" />
        <CardBody>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
            {formError && (
              <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--color-danger-bg)', border: '1px solid var(--color-danger-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-danger)', fontSize: 'var(--text-sm)' }}>
                {formError}
              </div>
            )}

            {resultMessage && (
              <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--color-success-bg)', border: '1px solid var(--color-success-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-success)', fontSize: 'var(--text-sm)' }}>
                Successfully updated {resultMessage.updated} student marks records!
                {resultMessage.errors.length > 0 && (
                  <ul style={{ marginTop: 'var(--space-2)', color: 'var(--color-warning)' }}>
                    {resultMessage.errors.map((err, i) => (
                      <li key={i}>
                        {typeof err === 'string' ? err : `Student #${err.student_id}: ${err.error}`}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div>
              <label htmlFor="assignment-select" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
                Teaching Assignment *
              </label>
              <select
                id="assignment-select"
                value={selectedAssignmentId}
                onChange={(e) => setSelectedAssignmentId(e.target.value ? Number(e.target.value) : '')}
                required
              >
                <option value="">-- Choose Subject & Batch --</option>
                {assignments.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.subject_code} - {a.subject_name} ({a.batch_name}, Sem {a.semester}, Max: {a.internal_max})
                  </option>
                ))}
              </select>
            </div>

            {activeAssignment && (
              <div style={{ marginTop: 'var(--space-2)' }}>
                <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--space-3)' }}>
                  Student Marks Entry Grid (Max Marks: {activeAssignment.internal_max})
                </h4>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                  {rows.map((row, index) => (
                    <div key={index} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 'var(--space-3)', alignItems: 'center' }}>
                      <input
                        type="number"
                        placeholder="Student ID (e.g. 101)"
                        value={row.studentId}
                        onChange={(e) => handleRowChange(index, 'studentId', e.target.value)}
                        required={index === 0}
                      />
                      <input
                        type="number"
                        step="0.5"
                        min="0"
                        max={activeAssignment.internal_max}
                        placeholder={`Marks (0 - ${activeAssignment.internal_max})`}
                        value={row.marks}
                        onChange={(e) => handleRowChange(index, 'marks', e.target.value)}
                        required={index === 0}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={rows.length <= 1}
                        onClick={() => handleRemoveRow(index)}
                      >
                        ✕
                      </Button>
                    </div>
                  ))}
                </div>

                <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-4)' }}>
                  <Button type="button" variant="outline" size="sm" onClick={handleAddRow}>
                    + Add Student Row
                  </Button>
                  <Button type="submit" variant="primary" size="sm" isLoading={saveMarksMutation.isPending}>
                    Submit Assessment Marks
                  </Button>
                </div>
              </div>
            )}
          </form>
        </CardBody>
      </Card>
    </div>
  );
};
