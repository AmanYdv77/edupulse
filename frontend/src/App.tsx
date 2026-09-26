import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { RouteGuard } from './components/RouteGuard';
import { AppLayout } from './components/Layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { UnauthorizedPage } from './pages/UnauthorizedPage';
import { NotFoundPage } from './pages/NotFoundPage';

// Role-Based Screen Components
import { StudentDashboard } from './features/student/StudentDashboard';
import { StudentResults } from './features/student/StudentResults';
import { HabitCheckIn } from './features/student/HabitCheckIn';
import { TeacherClassesView } from './features/teacher/TeacherClassesView';
import { AtRiskRosterView } from './features/teacher/AtRiskRosterView';
import { InternalMarksEntry } from './features/teacher/InternalMarksEntry';
import { ScopeAnalyticsView } from './features/analytics/ScopeAnalyticsView';
import { ModelRegistryView } from './features/admin/ModelRegistryView';

import './styles/base.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter basename="/app">
          <Routes>
            {/* Public Routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/unauthorized" element={<UnauthorizedPage />} />

            {/* Protected Routes inside AppLayout */}
            <Route
              path="/"
              element={
                <RouteGuard>
                  <AppLayout />
                </RouteGuard>
              }
            >
              <Route index element={<DashboardPage />} />

              {/* Student Routes */}
              <Route
                path="student/dashboard"
                element={
                  <RouteGuard requiredCapability="view_own_results">
                    <StudentDashboard />
                  </RouteGuard>
                }
              />
              <Route
                path="student/results"
                element={
                  <RouteGuard requiredCapability="view_own_results">
                    <StudentResults />
                  </RouteGuard>
                }
              />
              <Route
                path="student/habits"
                element={
                  <RouteGuard requiredCapability="log_habits">
                    <HabitCheckIn />
                  </RouteGuard>
                }
              />

              {/* Analytics & Rosters (Teacher, HOD, Dean, Executive) */}
              <Route
                path="analytics"
                element={
                  <RouteGuard requiredCapability="view_analytics">
                    <ScopeAnalyticsView />
                  </RouteGuard>
                }
              />
              <Route
                path="classes"
                element={
                  <RouteGuard requiredCapability="view_analytics">
                    <TeacherClassesView />
                  </RouteGuard>
                }
              />
              <Route
                path="roster"
                element={
                  <RouteGuard requiredCapability="view_at_risk_roster">
                    <AtRiskRosterView />
                  </RouteGuard>
                }
              />

              {/* Faculty Marks Entry */}
              <Route
                path="marks"
                element={
                  <RouteGuard requiredCapability="enter_internal_marks">
                    <InternalMarksEntry />
                  </RouteGuard>
                }
              />

              {/* Admin Model Registry */}
              <Route
                path="models"
                element={
                  <RouteGuard requiredCapability="manage_model_registry">
                    <ModelRegistryView />
                  </RouteGuard>
                }
              />
            </Route>

            {/* 404 Catch-All */}
            <Route path="/404" element={<NotFoundPage />} />
            <Route path="*" element={<Navigate to="/404" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
