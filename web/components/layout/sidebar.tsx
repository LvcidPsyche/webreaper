'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { clsx } from 'clsx';
import {
  LayoutDashboard,
  Play,
  Shield,
  MessageSquare,
  FlaskConical,
  Settings,
  Network,
  ScrollText,
  Database,
  FolderOpen,
  ShieldCheck,
  Repeat,
  Crosshair,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

const navItems = [
  { href: '/',            label: 'Dashboard',  icon: LayoutDashboard, code: '01' },
  { href: '/jobs',        label: 'Jobs',        icon: Play,            code: '02' },
  { href: '/data',        label: 'Data',        icon: Database,        code: '03' },
  { href: '/workspaces',  label: 'Workspaces',  icon: FolderOpen,      code: '04' },
  { href: '/security',    label: 'Security',    icon: Shield,          code: '05' },
  { href: '/topology',    label: 'Topology',    icon: Network,         code: '06' },
  { href: '/proxy',       label: 'Proxy',       icon: ShieldCheck,     code: '07' },
  { href: '/repeater',    label: 'Repeater',    icon: Repeat,          code: '08' },
  { href: '/intruder',    label: 'Intruder',    icon: Crosshair,       code: '09' },
  { href: '/workstation', label: 'Workstation', icon: FlaskConical,    code: '10' },
  { href: '/chat',        label: 'Chat',        icon: MessageSquare,   code: '11' },
  { href: '/logs',        label: 'Logs',        icon: ScrollText,      code: '12' },
  { href: '/settings',    label: 'Settings',    icon: Settings,        code: '13' },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={clsx(
        'h-screen bg-ghost-surface border-r border-ghost-border flex flex-col transition-all duration-200 ease-out shrink-0',
        collapsed ? 'w-14' : 'w-52'
      )}
    >
      {/* Wordmark */}
      <div className={clsx(
        'flex items-center border-b border-ghost-border shrink-0 h-12',
        collapsed ? 'justify-center' : 'px-4 gap-2'
      )}>
        {collapsed ? (
          <span className="text-ghost-green font-mono font-bold text-base tracking-widest select-none">W</span>
        ) : (
          <>
            <span className="text-ghost-green font-mono font-bold text-sm tracking-[0.2em] select-none">WEB</span>
            <span className="text-ghost-dim font-mono text-sm tracking-[0.2em] select-none">REAPER</span>
          </>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {navItems.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                'group relative flex items-center h-10 transition-colors duration-100',
                collapsed ? 'justify-center' : 'px-4 gap-3',
                active ? 'text-ghost-green' : 'text-ghost-dim hover:text-ghost-text'
              )}
            >
              {/* Active left bar */}
              {active && (
                <span className="absolute left-0 top-2 bottom-2 w-[2px] bg-ghost-green" />
              )}
              {collapsed ? (
                <item.icon className="w-3.5 h-3.5 shrink-0" />
              ) : (
                <>
                  <span className={clsx(
                    'text-[10px] font-mono tabular-nums shrink-0 w-5',
                    active ? 'text-ghost-green' : 'text-ghost-label'
                  )}>
                    {item.code}
                  </span>
                  <span className="text-xs font-mono uppercase tracking-widest">{item.label}</span>
                </>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className={clsx(
          'flex items-center justify-center border-t border-ghost-border text-ghost-dim hover:text-ghost-text transition-colors duration-100 shrink-0 h-9',
          !collapsed && 'gap-2 px-4'
        )}
      >
        {collapsed
          ? <ChevronRight className="w-3 h-3" />
          : (
            <>
              <ChevronLeft className="w-3 h-3" />
              <span className="text-[10px] font-mono uppercase tracking-widest">Collapse</span>
            </>
          )
        }
      </button>
    </aside>
  );
}
