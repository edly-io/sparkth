/**
 * The dashboard page core serves for a plugin, at `app/dashboard/[pluginName]/`.
 *
 * Build links to a plugin's page with this rather than writing the route out, so the route has one owner.
 */
export function pluginPath(name: string): string {
  return `/dashboard/${name}`;
}
