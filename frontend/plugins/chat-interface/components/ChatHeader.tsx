export function ChatHeader() {
  return (
    <div className="border-b border-border px-6 py-4">
      <div className="flex items-center gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            AI Course Creator
          </h2>
          <p className="text-sm text-muted-foreground">
            Transform your resources into courses with AI
          </p>
        </div>
      </div>
    </div>
  );
}
