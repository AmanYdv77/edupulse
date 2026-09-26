import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { StatCard } from '../../components/ui/StatCard';
import { Badge } from '../../components/ui/Badge';
import { ModelLabel } from '../../components/ui/ModelLabel';
import { Skeleton } from '../../components/ui/Skeleton';
import { ErrorState } from '../../components/ui/ErrorState';
import { EmptyState } from '../../components/ui/EmptyState';

export const StudentDashboard: React.FC = () => {
  const { user } = useAuth();
  const studentId = user?.id || 0;

  const {
    data: predictionData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['student-predictions', studentId],
    queryFn: async () => {
      const { data, error: apiErr } = await apiClient.GET('/api/v1/students/{id}/predictions/', {
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
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-4)' }}>
          <Skeleton height="7rem" />
          <Skeleton height="7rem" />
          <Skeleton height="7rem" />
        </div>
        <Skeleton height="15rem" />
      </div>
    );
  }

  if (error) {
    return <ErrorState title="Failed to load performance prediction" onRetry={() => refetch()} />;
  }

  const predictions = predictionData?.predictions || [];

  if (!predictionData || predictions.length === 0) {
    return <EmptyState title="No prediction available" description="Complete your habit check-in to generate a score forecast." />;
  }

  const targetSemester = predictionData.target_semester;
  const highRiskCount = predictions.filter((p) => p.risk_band === 'high').length;
  const avgForecast =
    predictions.filter((p) => p.predicted_score !== null).reduce((acc, p) => acc + (p.predicted_score || 0), 0) /
    (predictions.filter((p) => p.predicted_score !== null).length || 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-4)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700 }}>Academic Performance Forecast</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>
            Real-time advisory score predictions for Semester {targetSemester}
          </p>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-4)' }}>
        <StatCard
          label="Overall Average Forecast"
          value={isNaN(avgForecast) ? 'N/A' : `${avgForecast.toFixed(1)}%`}
          subtitle={`Semester ${targetSemester} target`}
          icon="🎯"
        />
        <StatCard
          label="Subjects Tracked"
          value={`${predictions.length} Subjects`}
          subtitle={highRiskCount > 0 ? `${highRiskCount} subjects flagged at-risk` : 'All subjects on track'}
          icon="📚"
        />
        <StatCard
          label="Advisory Risk Status"
          value={<Badge riskBand={highRiskCount > 0 ? 'high' : 'low'} />}
          subtitle="Updated dynamically from habit logs"
          icon="🛡️"
        />
      </div>

      {/* Subject Prediction Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 600 }}>Subject Predictions & Insights</h3>

        {predictions.map((p, idx) => {
          const isSufficient = !p.insufficient_data;
          const riskBand = p.risk_band || (isSufficient ? 'low' : 'insufficient_data');
          const factors = p.factors || [];

          return (
            <Card key={`pred-${p.subject_code}-${idx}`}>
              <CardHeader
                title={`${p.subject_name} (${p.subject_code})`}
                subtitle={`Target Semester ${p.semester}`}
                action={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                    <ModelLabel slot="baseline" version={p.model_version || 1} algorithm={p.model_label} isActive={true} />
                    <Badge riskBand={riskBand} />
                  </div>
                }
              />
              <CardBody>
                {!isSufficient ? (
                  <div style={{ padding: 'var(--space-4)', backgroundColor: 'var(--risk-insufficient-bg)', borderRadius: 'var(--radius-md)' }}>
                    <h4 style={{ color: 'var(--risk-insufficient-text)', fontWeight: 600, marginBottom: 'var(--space-2)' }}>
                      ℹ️ Insufficient Habit Data for this Subject
                    </h4>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-2)' }}>
                      Complete your weekly habit check-in to generate an accurate score prediction. No invented scores are generated.
                    </p>
                    {p.insufficient_data_reasons && p.insufficient_data_reasons.length > 0 && (
                      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
                        Reasons: {p.insufficient_data_reasons.join('; ')}
                      </p>
                    )}
                  </div>
                ) : (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
                      <span style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                        {p.predicted_score !== null ? `${p.predicted_score.toFixed(1)}%` : 'N/A'}
                      </span>
                      {p.confidence_score !== null && (
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
                          (Confidence: {(p.confidence_score * 100).toFixed(0)}%)
                        </span>
                      )}
                    </div>

                    {factors.length > 0 && (
                      <div>
                        <h5 style={{ fontSize: 'var(--text-xs)', fontWeight: 600, textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 'var(--space-2)' }}>
                          Key Driver Factors
                        </h5>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                          {factors.map((f, fIdx) => (
                            <span
                              key={fIdx}
                              style={{
                                padding: 'var(--space-1) var(--space-2)',
                                backgroundColor: 'var(--color-surface-elevated)',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: 'var(--text-xs)',
                              }}
                            >
                              {(f.name || f.feature)}: {f.impact} {f.description ? `(${f.description})` : ''}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardBody>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
