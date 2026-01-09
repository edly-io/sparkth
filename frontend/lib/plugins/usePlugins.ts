import { useEffect, useState } from 'react';
import { getPluginsByNames, PluginDefinition } from './registry';

export function usePlugins(token: string | null) {
  const [enabledPlugins, setEnabledPlugins] = useState<PluginDefinition[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadPlugins() {
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const response = await fetch('/api/v1/user-plugins/', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const userPlugins = await response.json();
          const enabledNames = userPlugins
            .filter((p: any) => p.enabled)
            .map((p: any) => p.plugin_name);

          const plugins = getPluginsByNames(enabledNames);
          setEnabledPlugins(plugins);
        }
      } catch (error) {
        console.error('Failed to load plugins:', error);
      } finally {
        setLoading(false);
      }
    }

    loadPlugins();
  }, [token]);

  return { enabledPlugins, loading };
}