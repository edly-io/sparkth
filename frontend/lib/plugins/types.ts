import { ComponentType } from 'react';

export interface PluginConfig {
  [key: string]: any;
}

export interface PluginRoute {
  path: string;
  label: string;
  icon?: ComponentType<{ className?: string }>;
}

export interface PluginDefinition {
  name: string;
  displayName: string;
  description?: string;
  isCore?: boolean;
  
  loadComponent: () => Promise<{ default: ComponentType<any> }>;
  
  routes?: PluginRoute[];
  
  showInSidebar?: boolean;
  sidebarIcon?: ComponentType<{ className?: string }>;
  sidebarLabel?: string;
  sidebarOrder?: number;
}

export interface EnabledPlugin {
  name: string;
  config: PluginConfig;
  enabled: boolean;
}