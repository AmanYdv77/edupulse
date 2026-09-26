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
import { CapabilityPlaceholderPage } from './pages/CapabilityPlaceholderPage';
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

              <Route
                path="student/results"
                element={
                  <RouteGuard requiredCapability="view_own_results">
                    <CapabilityPlaceholderPage
                      title="Academic Results"
                      capability="view_own_results"
                      description="Semester results, SGPA, grades, and marks cards."
                    />
                  </RouteGuard>
                }
              />

              <Route
                path="student/habits"
                element={
                  <RouteGuard requiredCapability="log_habits">
                    <CapabilityPlaceholderPage
                      title="Daily & Weekly Habit Check-In"
                      capability="log_habits"
                      description="Study hours, sleep, attendance, and routine trackers."
                    />
                  </RouteGuard>
                }
              />

              <Route
                path="analytics"
                element={
                  <RouteGuard requiredCapability="view_analytics">
                    <CapabilityPlaceholderPage
                      title="Institutional Analytics"
                      capability="view_analytics"
                      description="Scoped performance KPIs, cohort breakdown, and longitudinal trends."
                    />
                  </RouteGuard>
                }
              />

              <Route
                path="roster"
                element={
                  <RouteGuard requiredCapability="view_at_risk_roster">
                    <CapabilityPlaceholderPage
                      title="At-Risk Student Roster"
                      capability="view_at_risk_roster"
                      description="Scoped early-warning roster and explanation factors."
                    />
                  </RouteGuard>
                }
              />

              <Route
                path="marks"
                element={
                  <RouteGuard requiredCapability="enter_internal_marks">
                    <CapabilityPlaceholderPage
                      title="Internal Marks Entry"
                      capability="enter_internal_marks"
                      description="Spreadsheet grid and CSV bulk marks upload."
                    />
                  </RouteGuard>
                }
              />

              <Route
                path="models"
                element={
                  <RouteGuard requiredCapability="manage_model_registry">
                    <CapabilityPlaceholderPage
                      title="Model Registry"
                      capability="manage_model_registry"
                      description="Algorithm versioning, holdout metrics, and activation controls."
                    />
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
