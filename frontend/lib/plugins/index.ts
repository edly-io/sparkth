import { registerPlugin } from './registry';
import { chatPlugin } from './chat-interface';

registerPlugin(chatPlugin);

export * from './registry';
export * from './types';
export * from './usePlugins'; 