/** A date for display in the user's locale, or "-" when there is none. */
export function formatDate(dateString?: string | null): string {
  if (!dateString) return "-";
  return new Date(dateString).toLocaleDateString();
}
