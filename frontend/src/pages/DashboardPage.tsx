import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardHeader, CardBody } from '../components/ui/Card';
import { StatCard } from '../components/ui/StatCard';
import { ModelLabel } from '../components/ui/ModelLabel';
import { Badge } from '../components/ui/Badge';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Welcome Banner */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--space-4)',
        }}
      >
        <div>
          <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            Welcome back, {user?.display_name || 'User'}
          </h1>
          <p style={{ color: 'var(--color-text-muted)', marginTop: 'var(--space-1)' }}>
            EduPulse Academic Intelligence & Performance Prediction Platform
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <ModelLabel slot="baseline" version={1} algorithm="Ridge (α=1.0)" isActive={true} />
        </div>
      </div>

      {/* Scope Details Card */}
      <Card>
        <CardHeader
          title="Session Scope & Academic Access"
          subtitle="Server-derived authorization profile"
          action={<Badge variant="info">{user?.role || 'STUDENT'}</Badge>}
        />
        <CardBody>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 'var(--space-4)',
            }}
          >
            <StatCard
              label="Academic Scope"
              value={user?.scope_label || 'Default Scope'}
              subtitle="Derived from institutional assignments"
              icon="🏫"
            />
            <StatCard
              label="Active Capabilities"
              value={`${user?.capabilities?.length || 0} Permissions`}
              subtitle="Granular API authorization tokens"
              icon="🔑"
            />
            <StatCard
              label="Session Security"
              value="HttpOnly Cookie"
              subtitle="Same-origin protected credentials"
              icon="🛡️"
            />
          </div>
        </CardBody>
      </Card>
    </div>
  );
};
