'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Settings } from 'lucide-react';
import { PluginDefinition } from '@/lib/plugins/types';

interface AppSidebarProps {
  plugins: PluginDefinition[];
}

export default function AppSidebar({ plugins }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="w-64 bg-white border-r flex flex-col">
      <div className="p-4 border-b">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="font-semibold text-lg">Sparkth</span>
        </Link>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Navigation
        </p>
        
        {plugins.map((plugin) => {
          const Icon = plugin.sidebarIcon;
          const isActive = pathname === `/${plugin.name}` || pathname?.startsWith(`/${plugin.name}/`);
          
          return (
            <Link
              key={plugin.name}
              href={`${plugin.name}`}
              className=
                {`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
                ${isActive
                  ? 'bg-blue-50 text-blue-600'
                  : 'text-gray-700 hover:bg-gray-100'
                }`}
            >
              {Icon && <Icon className="w-5 h-5" />}
              <span className="font-medium">{plugin.sidebarLabel}</span>
            </Link>
          );
        })}

        <Link
          href="settings/plugins"
          className={
            `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
            ${pathname === '/settings/plugins'
              ? 'bg-blue-50 text-blue-600'
              : 'text-gray-700 hover:bg-gray-100'
            }`}
        >
          <Settings className="w-5 h-5" />
          <span className="font-medium">Settings</span>
        </Link>
      </nav>

      <div className="p-4 border-t">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
            <span className="text-sm">👤</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">User</p>
            <p className="text-xs text-gray-500">Free Plan</p>
          </div>
        </div>
      </div>
    </div>
  );
}