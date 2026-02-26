'use client';

import { useEffect, useRef, useState } from 'react';

interface CounterProps {
  value: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
}

export function Counter({
  value,
  duration = 0,
  decimals = 0,
  prefix = '',
  suffix = '',
  className,
}: CounterProps) {
  const [display, setDisplay] = useState(value);
  const prevRef = useRef(0);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    if (duration <= 0) {
      prevRef.current = value;
      setDisplay(value);
      return;
    }
    const start = prevRef.current;
    const diff = value - start;
    const startTime = performance.now();

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + diff * eased;

      setDisplay(current);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        prevRef.current = value;
      }
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [value, duration]);

  const formatted = decimals > 0
    ? display.toFixed(decimals)
    : Math.round(display).toLocaleString();

  return (
    <span className={className}>
      {prefix}{formatted}{suffix}
    </span>
  );
}
