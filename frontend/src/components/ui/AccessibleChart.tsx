import React, { useState } from 'react';
import { Button } from './Button';
import { DataTable } from './DataTable';
import './AccessibleChart.css';

export interface AccessibleChartProps<T = Record<string, unknown>> {
  title: string;
  description?: string;
  tableColumns: Array<{ key: string; header: string; render?: (item: T) => React.ReactNode }>;
  tableData: T[];
  keyExtractor: (item: T, index: number) => string | number;
  children: React.ReactNode;
}

export function AccessibleChart<T = Record<string, unknown>>({
  title,
  description,
  tableColumns,
  tableData,
  keyExtractor,
  children,
}: AccessibleChartProps<T>): React.ReactElement {
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart');

  return (
    <div className="accessible-chart-container" role="region" aria-label={title}>
      <div className="chart-toolbar">
        <div>
          <h4 className="chart-title">{title}</h4>
          {description && (
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
              {description}
            </p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setViewMode(viewMode === 'chart' ? 'table' : 'chart')}
          aria-pressed={viewMode === 'table'}
        >
          {viewMode === 'chart' ? 'View as Data Table' : 'View as Visual Chart'}
        </Button>
      </div>

      {viewMode === 'chart' ? (
        <div className="chart-wrapper">{children}</div>
      ) : (
        <div className="chart-table-fallback">
          <DataTable
            columns={tableColumns}
            data={tableData}
            keyExtractor={keyExtractor}
          />
        </div>
      )}
    </div>
  );
}
