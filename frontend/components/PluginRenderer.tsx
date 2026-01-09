'use client';

import { Suspense, lazy, useMemo } from 'react';
import { PluginDefinition, PluginConfig } from '@/lib/plugins/types';

interface PluginRendererProps {
  pluginDef: PluginDefinition;
  config: PluginConfig;
}

export default function PluginRenderer({ pluginDef, config }: PluginRendererProps) {
  const PluginComponent = useMemo(
    () => lazy(() => pluginDef.loadComponent()),
    [pluginDef]
  );

  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading {pluginDef.displayName}...</p>
          </div>
        </div>
      }
    >
      <PluginComponent config={config} />
    </Suspense>
  );
}