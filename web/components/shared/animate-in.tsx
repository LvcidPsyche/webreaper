'use client';

import { type HTMLAttributes, type ReactNode } from 'react';

interface AnimateInProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  delay?: number;
  duration?: number;
  direction?: 'up' | 'down' | 'left' | 'right' | 'none';
  className?: string;
}

export function AnimateIn({
  children,
  delay = 0, // kept for API compatibility
  duration = 0.2, // kept for API compatibility
  direction = 'up', // kept for API compatibility
  className,
  ...props
}: AnimateInProps) {
  return (
    <div className={className} {...props}>
      {children}
    </div>
  );
}
