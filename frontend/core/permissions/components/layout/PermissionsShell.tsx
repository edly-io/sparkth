/** The frame every Access & permissions page sits in. */
export function PermissionsShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">{children}</div>
    </div>
  );
}
