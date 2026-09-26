import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card, CardBody } from '../components/ui/Card';

export const NotFoundPage: React.FC = () => {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem 1rem' }}>
      <Card style={{ maxWidth: '500px', width: '100%', textAlign: 'center' }}>
        <CardBody style={{ padding: '3rem 2rem' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔍</div>
          <h2 style={{ fontSize: 'var(--text-xl)', marginBottom: '0.5rem' }}>404 - Page Not Found</h2>
          <p style={{ color: 'var(--color-text-muted)', marginBottom: '2rem' }}>
            The requested page does not exist or has moved.
          </p>
          <Link to="/">
            <Button variant="primary">Return to Home</Button>
          </Link>
        </CardBody>
      </Card>
    </div>
  );
};
