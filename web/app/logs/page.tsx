'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { ScrollText, Pause, Play, Trash2, Filter } from 'lucide-react';
import { clsx } from 'clsx';
import { AnimateIn } from '@/components/shared/animate-in';
import { useSSE } from '@/hooks/use-sse';
import { LOG_LEVEL_COLORS } from '@/lib/constants';
import type { LogEntry } from '@/lib/types';

type LevelFilter = 'all' | LogEntry['level'];
const MAX_LOGS = 500;

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState<LevelFilter>('all');
  const [sourceFilter, setSourceFilter] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const autoScroll = useRef(true);

  const handleLog = useCallback((entry: LogEntry) => {
    if (paused) return;
    setLogs((prev) => [...prev, entry].slice(-MAX_LOGS));
  }, [paused]);

  useSSE<LogEntry>({ path: '/stream/logs', onEvent: handleLog });

  useEffect(() => {
    if (autoScroll.current && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    autoScroll.current = scrollHeight - scrollTop - clientHeight < 40;
  };

  const filtered = logs.filter((log) => {
    if (filter !== 'all' && log.level !== filter) return false;
    if (sourceFilter && !log.source.toLowerCase().includes(sourceFilter.toLowerCase())) return false;
    return true;
  });
  const sources = [...new Set(logs.map((l) => l.source))];

  return (
    <div className="space-y-3 h-[calc(100vh-8rem)] flex flex-col">
      <AnimateIn>
        <div className="flex items-center justify-between">
          <h1 className="text-sm font-mono text-white flex items-center gap-2">
            <ScrollText className="w-4 h-4 text-reaper-accent" /> Live Logs
            <span className="text-xs text-reaper-muted">({filtered.length})</span>
          </h1>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 border border-reaper-border rounded overflow-hidden">
              {(['all', 'error', 'warn', 'info', 'debug'] as const).map((level) => (
                <button key={level} onClick={() => setFilter(level)} className={clsx('px-2 py-1 text-[10px] font-mono uppercase transition-colors', filter === level ? 'bg-reaper-border text-white' : 'text-reaper-muted hover:text-white')}>
                  {level}
                </button>
              ))}
            </div>
            {sources.length > 0 && (
              <div className="flex items-center gap-1">
                <Filter className="w-3 h-3 text-reaper-muted" />
                <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="bg-reaper-surface border border-reaper-border rounded px-2 py-1 text-[10px] font-mono text-white focus:border-reaper-accent outline-none">
                  <option value="">All Sources</option>
                  {sources.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            )}
            <button onClick={() => setPaused(!paused)} className={clsx('p-1.5 rounded transition-colors', paused ? 'text-reaper-warning' : 'text-reaper-muted hover:text-white')} title={paused ? 'Resume' : 'Pause'}>
              {paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
            </button>
            <button onClick={() => setLogs([])} className="p-1.5 text-reaper-muted hover:text-reaper-danger transition-colors rounded" title="Clear logs">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </AnimateIn>

      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 bg-reaper-surface border border-reaper-border rounded-lg overflow-y-auto font-mono text-xs">
        {filtered.length === 0 ? (
          <div className="flex items-center justify-center h-full text-reaper-muted">
            {paused ? 'Paused' : 'Waiting for log events...'}
          </div>
        ) : (
          <div className="p-2 space-y-px">
            {filtered.map((log, i) => (
              <div key={log.id || i} className="flex gap-2 py-0.5 px-2 rounded hover:bg-reaper-border/20">
                <span className="text-reaper-muted shrink-0 w-[72px]">{new Date(log.timestamp).toLocaleTimeString()}</span>
                <span className="uppercase shrink-0 w-[44px] text-right" style={{ color: LOG_LEVEL_COLORS[log.level] || '#666680' }}>{log.level}</span>
                <span className="text-reaper-accent shrink-0 w-[80px] truncate">[{log.source}]</span>
                <span className="text-gray-300 break-all">{log.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
