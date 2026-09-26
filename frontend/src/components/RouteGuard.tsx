import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Skeleton } from './ui/Skeleton';

export interface RouteGuardProps {
  children: React.ReactElement;
  requiredCapability?: string;
}

export const RouteGuard: React.FC<RouteGuardProps> = ({ children, requiredCapability }) => {
  const { isAuthenticated, isLoading, hasCapability } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <Skeleton height="3rem" />
        <Skeleton height="12rem" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredCapability && !hasCapability(requiredCapability)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};
