import React from 'react';
import { Card, CardHeader, CardBody } from '../components/ui/Card';

interface CapabilityPageProps {
  title: string;
  capability: string;
  description: string;
}

export const CapabilityPlaceholderPage: React.FC<CapabilityPageProps> = ({
  title,
  capability,
  description,
}) => {
  return (
    <Card>
      <CardHeader title={title} subtitle={`Protected by capability: ${capability}`} />
      <CardBody>
        <p style={{ color: 'var(--color-text-muted)' }}>{description}</p>
      </CardBody>
    </Card>
  );
};
