import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, refreshCsrf } from '../../api/client';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { DataTable } from '../../components/ui/DataTable';
import { Badge } from '../../components/ui/Badge';
import { Skeleton } from '../../components/ui/Skeleton';
import { ErrorState } from '../../components/ui/ErrorState';

interface HabitLogItem {
  id: number;
  log_type: 'DAILY' | 'WEEKLY';
  log_date: string;
  hours_studied?: number | null;
  sleep_hours?: number | null;
  motivation_level?: string | null;
  physical_activity?: number | null;
  tutoring_sessions?: number | null;
  notes?: string | null;
}

export const HabitCheckIn: React.FC = () => {
  const queryClient = useQueryClient();

  const today = new Date().toISOString().split('T')[0];

  const [logType, setLogType] = useState<'DAILY' | 'WEEKLY'>('DAILY');
  const [logDate, setLogDate] = useState(today);
  const [hoursStudied, setHoursStudied] = useState<number | ''>('');
  const [sleepHours, setSleepHours] = useState<number | ''>('');
  const [physicalActivity, setPhysicalActivity] = useState<number | ''>('');
  const [tutoringSessions, setTutoringSessions] = useState<number | ''>('');
  const [motivationLevel, setMotivationLevel] = useState<'Low' | 'Medium' | 'High' | ''>('Medium');
  const [notes, setNotes] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Fetch past habit check-in logs
  const { data: habitsData, isLoading, error, refetch } = useQuery({
    queryKey: ['student-habits'],
    queryFn: async () => {
      const { data, error: apiErr } = await apiClient.GET('/api/v1/habits/check-ins/');
      if (apiErr) throw apiErr;
      return data;
    },
  });

  const checkInMutation = useMutation({
    mutationFn: async (payload: {
      log_type: 'DAILY' | 'WEEKLY';
      log_date: string;
      hours_studied: number;
      sleep_hours: number;
      physical_activity?: number;
      tutoring_sessions?: number;
      motivation_level?: 'Low' | 'Medium' | 'High' | null;
      notes?: string;
    }) => {
      await refreshCsrf();
      const { data, error: apiErr } = await apiClient.POST('/api/v1/habits/check-ins/', {
        body: payload,
      });
      if (apiErr) throw apiErr;
      return data;
    },
    onSuccess: () => {
      setSuccessMessage('Habit check-in recorded successfully! Performance prediction updated.');
      setFormError(null);
      // Invalidate predictions and habits cache so student dashboard immediately updates
      queryClient.invalidateQueries({ queryKey: ['student-predictions'] });
      queryClient.invalidateQueries({ queryKey: ['student-habits'] });
      // Reset form
      setHoursStudied('');
      setSleepHours('');
      setPhysicalActivity('');
      setTutoringSessions('');
      setNotes('');
    },
    onError: (err: unknown) => {
      const msg =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : err instanceof Error
            ? err.message
            : 'Failed to submit habit check-in.';
      setFormError(msg);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccessMessage(null);

    const study = Number(hoursStudied);
    const sleep = Number(sleepHours);
    const activity = physicalActivity !== '' ? Number(physicalActivity) : 0;
    const tutoring = tutoringSessions !== '' ? Number(tutoringSessions) : 0;

    // Strict boundary validation matching ML contract
    if (isNaN(study) || study < 0 || study > 16) {
      setFormError('Study hours must be between 0.0 and 16.0 hours.');
      return;
    }
    if (isNaN(sleep) || sleep < 0 || sleep > 16) {
      setFormError('Sleep hours must be between 0.0 and 16.0 hours.');
      return;
    }
    if (activity < 0 || activity > 16) {
      setFormError('Physical activity must be between 0.0 and 16.0 hours.');
      return;
    }
    if (tutoring < 0 || tutoring > 20) {
      setFormError('Tutoring sessions must be between 0 and 20.');
      return;
    }

    checkInMutation.mutate({
      log_type: logType,
      log_date: logDate,
      hours_studied: study,
      sleep_hours: sleep,
      physical_activity: activity,
      tutoring_sessions: tutoring,
      motivation_level: (motivationLevel as 'Low' | 'Medium' | 'High') || null,
      notes: notes.trim() || undefined,
    });
  };

  const logs = (habitsData?.results || []) as unknown as HabitLogItem[];

  const columns = [
    { key: 'log_date', header: 'Date' },
    { key: 'log_type', header: 'Type', render: (row: HabitLogItem) => <Badge variant="neutral">{row.log_type}</Badge> },
    { key: 'hours_studied', header: 'Study (hrs)', render: (row: HabitLogItem) => row.hours_studied ?? '-' },
    { key: 'sleep_hours', header: 'Sleep (hrs)', render: (row: HabitLogItem) => row.sleep_hours ?? '-' },
    { key: 'motivation_level', header: 'Motivation', render: (row: HabitLogItem) => row.motivation_level || '-' },
    { key: 'physical_activity', header: 'Exercise (hrs)', render: (row: HabitLogItem) => row.physical_activity ?? '-' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700 }}>Study Habits & Routine Check-In</h1>
        <p style={{ color: 'var(--color-text-muted)' }}>
          Record your daily or weekly study habits to keep your forecast accurate
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-6)' }}>
        {/* Form Card */}
        <Card>
          <CardHeader title="Record New Check-In" subtitle="Honest habit tracking without invented values" />
          <CardBody>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              {formError && (
                <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--color-danger-bg)', border: '1px solid var(--color-danger-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-danger)', fontSize: 'var(--text-sm)' }}>
                  {formError}
                </div>
              )}
              {successMessage && (
                <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--color-success-bg)', border: '1px solid var(--color-success-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-success)', fontSize: 'var(--text-sm)' }}>
                  {successMessage}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                <div>
                  <label htmlFor="log-type-select" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
                    Log Type
                  </label>
                  <select id="log-type-select" value={logType} onChange={(e) => setLogType(e.target.value as 'DAILY' | 'WEEKLY')}>
                    <option value="DAILY">Daily Check-In</option>
                    <option value="WEEKLY">Weekly Summary</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="log-date-input" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
                    Log Date
                  </label>
                  <input id="log-date-input" type="date" value={logDate} onChange={(e) => setLogDate(e.target.value)} required />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                <div>
                  <label htmlFor="hours-studied-input" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
                    Hours Studied (0-16) *
                  </label>
                  <input id="hours-studied-input" type="number" step="0.5" min="0" max="16" placeholder="e.g. 4.5" value={hoursStudied} onChange={(e) => setHoursStudied(e.target.value === '' ? '' : Number(e.target.value))} required />
                </div>
                <div>
                  <label htmlFor="sleep-hours-input" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
                    Sleep Hours (0-16) *
                  </label>
                  <input id="sleep-hours-input" type="number" step="0.5" min="0" max="16" placeholder="e.g. 7.5" value={sleepHours} onChange={(e) => setSleepHours(e.target.value === '' ? '' : Number(e.target.value))} required />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                <div>
                  <label htmlFor="exercise-input" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
                    Exercise (hrs/day)
                  </label>
                  <input id="exercise-input" type="number" step="0.5" min="0" max="16" placeholder="e.g. 1.0" value={physicalActivity} onChange={(e) => setPhysicalActivity(e.target.value === '' ? '' : Number(e.target.value))} />
                </div>
                <div>
                  <label htmlFor="tutoring-input" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
                    Tutoring Sessions
                  </label>
                  <input id="tutoring-input" type="number" min="0" max="20" placeholder="e.g. 1" value={tutoringSessions} onChange={(e) => setTutoringSessions(e.target.value === '' ? '' : Number(e.target.value))} />
                </div>
              </div>

              <div>
                <label htmlFor="motivation-select" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
                  Motivation Level
                </label>
                <select id="motivation-select" value={motivationLevel} onChange={(e) => setMotivationLevel(e.target.value as 'Low' | 'Medium' | 'High')}>
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                </select>
              </div>

              <div>
                <label htmlFor="notes-input" style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
                  Reflections & Notes
                </label>
                <textarea id="notes-input" rows={2} placeholder="Optional study topics, exam preparations..." value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>

              <Button type="submit" variant="primary" size="lg" isLoading={checkInMutation.isPending}>
                Save Check-In
              </Button>
            </form>
          </CardBody>
        </Card>

        {/* History Table */}
        <Card>
          <CardHeader title="Check-In History" subtitle="Recent submissions" />
          <CardBody>
            {isLoading ? (
              <Skeleton height="10rem" />
            ) : error ? (
              <ErrorState title="Failed to load history" onRetry={() => refetch()} />
            ) : (
              <DataTable
                columns={columns}
                data={logs}
                keyExtractor={(item) => item.id}
                emptyMessage="No habit logs recorded yet. Submit your first check-in above!"
              />
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
};
