import { PluginDefinition } from '../types';
import { MessageSquare } from 'lucide-react';

export const chatPlugin: PluginDefinition = {
  name: 'chat-interface',
  displayName: 'AI Chat',
  description: 'Chat interface integration plugin',
  isCore: true,
  
  loadComponent: () => import('./ChatInterface'),
  
  showInSidebar: true,
  sidebarIcon: MessageSquare,
  sidebarLabel: 'Chat',
  sidebarOrder: 1,
};