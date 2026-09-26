import React from 'react';
import { useAuth } from '../context/AuthContext';
import { StudentDashboard } from '../features/student/StudentDashboard';
import { TeacherClassesView } from '../features/teacher/TeacherClassesView';
import { ScopeAnalyticsView } from '../features/analytics/ScopeAnalyticsView';
import { ModelRegistryView } from '../features/admin/ModelRegistryView';
import { Card, CardHeader, CardBody } from '../components/ui/Card';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const role = user?.role;

  if (role === 'STUDENT') {
    return <StudentDashboard />;
  }

  if (role === 'TEACHER') {
    return <TeacherClassesView />;
  }

  if (['HOD', 'DEAN', 'VICE_CHANCELLOR', 'REGISTRAR', 'CONTROLLER_OF_EXAMINATIONS'].includes(role || '')) {
    return <ScopeAnalyticsView />;
  }

  if (role === 'SYSTEM_ADMIN') {
    return <ModelRegistryView />;
  }

  return (
    <Card>
      <CardHeader title="Academic Intelligence Platform" subtitle={`Welcome, ${user?.display_name || 'User'}`} />
      <CardBody>
        <p style={{ color: 'var(--color-text-muted)' }}>
          Active academic scope: <strong>{user?.scope_label || 'Default'}</strong>
        </p>
      </CardBody>
    </Card>
  );
};
