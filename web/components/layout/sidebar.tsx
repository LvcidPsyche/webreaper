'use client';

import { useState } from 'react';
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
  ChevronLeft,
  ChevronRight,
  Skull,
} from 'lucide-react';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/jobs', label: 'Jobs', icon: Play },
  { href: '/security', label: 'Security', icon: Shield },
  { href: '/chat', label: 'Chat', icon: MessageSquare },
  { href: '/workstation', label: 'Workstation', icon: FlaskConical },
  { href: '/settings', label: 'Settings', icon: Settings },
  { href: '/topology', label: 'Topology', icon: Network },
  { href: '/logs', label: 'Logs', icon: ScrollText },
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
        'h-screen bg-reaper-surface border-r border-reaper-border flex flex-col transition-all duration-200 ease-out',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      <div className="flex items-center gap-2 p-4 border-b border-reaper-border">
        <Skull className="w-6 h-6 text-reaper-accent shrink-0" />
        {!collapsed && (
          <span className="font-mono font-bold text-white text-sm tracking-wide">
            WebReaper
          </span>
        )}
      </div>

      <nav className="flex-1 py-2 overflow-y-auto">
        {navItems.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                'flex items-center gap-3 px-4 py-2.5 mx-2 rounded text-sm font-mono transition-colors duration-150',
                active
                  ? 'bg-reaper-accent/10 text-reaper-accent'
                  : 'text-reaper-muted hover:text-white hover:bg-reaper-border/50'
              )}
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <button
        onClick={onToggle}
        className="flex items-center justify-center p-3 border-t border-reaper-border text-reaper-muted hover:text-white transition-colors duration-150"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </aside>
  );
}
