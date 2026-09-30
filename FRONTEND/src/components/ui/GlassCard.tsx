import React from 'react';
import styles from './GlassCard.module.css';

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export function GlassCard({
  elevated = false,
  padding = 'md',
  className = '',
  children,
  ...rest
}: GlassCardProps) {
  return (
    <div
      className={[
        styles.card,
        elevated ? styles.elevated : '',
        styles[`padding-${padding}`],
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      {...rest}
    >
      {children}
    </div>
  );
}
