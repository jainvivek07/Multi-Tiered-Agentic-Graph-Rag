import React from 'react';
import styles from './Badge.module.css';

type BadgeVariant = 'cyan' | 'violet' | 'emerald' | 'amber' | 'rose' | 'muted';

const ROUTE_VARIANT: Record<string, BadgeVariant> = {
  vector:     'cyan',
  graph:      'violet',
  hybrid:     'amber',
  cache_hit:  'emerald',
  blocked_by_guardrails: 'rose',
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  /** Automatically picks variant based on RAG route string */
  route?: string;
  size?: 'sm' | 'md';
}

export function Badge({ children, variant, route, size = 'sm' }: BadgeProps) {
  const v = variant ?? (route ? (ROUTE_VARIANT[route] ?? 'muted') : 'muted');
  return (
    <span className={[styles.badge, styles[v], styles[size]].join(' ')}>
      {children}
    </span>
  );
}
