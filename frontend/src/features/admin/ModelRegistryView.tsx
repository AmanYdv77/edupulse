import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, refreshCsrf } from '../../api/client';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { DataTable } from '../../components/ui/DataTable';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { ErrorState } from '../../components/ui/ErrorState';

interface ModelVersionItem {
  id: number;
  slot: string;
  version: number;
  is_active: boolean;
  trained_on?: string;
  n_train_rows?: number;
  n_test_rows?: number;
  metrics?: {
    rmse?: number;
    r2?: number;
    [key: string]: unknown;
  };
}

export const ModelRegistryView: React.FC = () => {
  const queryClient = useQueryClient();
  const [activatingId, setActivatingId] = useState<number | null>(null);
  const [confirmModalVersion, setConfirmModalVersion] = useState<ModelVersionItem | null>(null);
  const [feedback, setFeedback] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const { data: models, isLoading, error, refetch } = useQuery({
    queryKey: ['model-registry'],
    queryFn: async () => {
      const { data, error: apiErr } = await apiClient.GET('/api/v1/models/');
      if (apiErr) throw apiErr;
      return (data || []) as unknown as ModelVersionItem[];
    },
  });

  const activateMutation = useMutation({
    mutationFn: async (id: number) => {
      await refreshCsrf();
      const res = await fetch(`/api/v1/models/${id}/activate/`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (await apiClient.GET('/api/v1/csrf/')).data?.csrfToken || '',
        },
      });
      if (!res.ok) {
        const err = (await res.json()) as { detail?: string; error?: string };
        throw new Error(err?.detail || err?.error || 'Failed to activate model version.');
      }
      return res.json();
    },
    onSuccess: () => {
      setFeedback({ message: 'Model version activated successfully! Serving slot updated.', type: 'success' });
      setConfirmModalVersion(null);
      queryClient.invalidateQueries({ queryKey: ['model-registry'] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Activation failed.';
      setFeedback({ message: msg, type: 'error' });
      setConfirmModalVersion(null);
    },
  });

  const handleActivateClick = (version: ModelVersionItem) => {
    setConfirmModalVersion(version);
  };

  const handleConfirmActivation = () => {
    if (confirmModalVersion) {
      setActivatingId(confirmModalVersion.id);
      activateMutation.mutate(confirmModalVersion.id);
    }
  };

  const columns = [
    { key: 'slot', header: 'Slot', render: (row: ModelVersionItem) => <strong>{row.slot === 'baseline' ? 'Model A (Baseline)' : 'Model B (Institute)'}</strong> },
    { key: 'version', header: 'Version', render: (row: ModelVersionItem) => `v${row.version}` },
    {
      key: 'is_active',
      header: 'Active State',
      render: (row: ModelVersionItem) => (
        <Badge variant={row.is_active ? 'success' : 'neutral'}>
          {row.is_active ? '● Active' : 'Inactive'}
        </Badge>
      ),
    },
    { key: 'trained_on', header: 'Training Dataset / Provenance' },
    { key: 'n_train_rows', header: 'Train Size', render: (row: ModelVersionItem) => `${row.n_train_rows ?? 0} rows` },
    { key: 'n_test_rows', header: 'Test Size', render: (row: ModelVersionItem) => `${row.n_test_rows ?? 0} rows` },
    {
      key: 'metrics',
      header: 'Evaluation Metrics',
      render: (row: ModelVersionItem) => {
        const m = row.metrics || {};
        const rmse = m.rmse !== undefined ? `RMSE: ${Number(m.rmse).toFixed(2)}` : '';
        const r2 = m.r2 !== undefined ? `R²: ${Number(m.r2).toFixed(2)}` : '';
        return <span>{[rmse, r2].filter(Boolean).join(' | ') || '-'}</span>;
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row: ModelVersionItem) => {
        if (row.is_active) {
          return <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-success)' }}>Serving Live</span>;
        }
        return (
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleActivateClick(row)}
            isLoading={activateMutation.isPending && activatingId === row.id}
          >
            Activate Version
          </Button>
        );
      },
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <div>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700 }}>Machine Learning Model Registry</h1>
        <p style={{ color: 'var(--color-text-muted)' }}>
          Inspect registered model artifacts, holdout evaluation metrics, and active deployment slots
        </p>
      </div>

      {feedback && (
        <div
          style={{
            padding: 'var(--space-3) var(--space-4)',
            backgroundColor: feedback.type === 'success' ? 'var(--color-success-bg)' : 'var(--color-danger-bg)',
            border: `1px solid ${feedback.type === 'success' ? 'var(--color-success-border)' : 'var(--color-danger-border)'}`,
            borderRadius: 'var(--radius-md)',
            color: feedback.type === 'success' ? 'var(--color-success)' : 'var(--color-danger)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {feedback.message}
        </div>
      )}

      <Card>
        <CardHeader title="Registered Model Versions" subtitle="Transparent provenance and promotion tracking" />
        <CardBody>
          {isLoading ? (
            <Skeleton height="15rem" />
          ) : error ? (
            <ErrorState title="Failed to load model registry" onRetry={() => refetch()} />
          ) : (
            <DataTable
              columns={columns}
              data={models || []}
              keyExtractor={(item) => item.id}
              emptyMessage="No model versions registered in the database."
            />
          )}
        </CardBody>
      </Card>

      {/* Confirmation Modal */}
      {confirmModalVersion && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: 'var(--space-4)',
          }}
        >
          <Card style={{ maxWidth: '480px', width: '100%' }}>
            <CardHeader title="Confirm Model Activation" />
            <CardBody>
              <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
                Are you sure you want to activate <strong>{confirmModalVersion.slot} v{confirmModalVersion.version}</strong>?
                This will immediately route all student predictions in the <code>{confirmModalVersion.slot}</code> slot to this version artifact.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-3)' }}>
                <Button variant="ghost" onClick={() => setConfirmModalVersion(null)}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={handleConfirmActivation} isLoading={activateMutation.isPending}>
                  Confirm & Activate
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
};
