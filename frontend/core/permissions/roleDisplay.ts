/**
 * A role's name as people read it: each run of underscores becomes a space and the first letter is
 * capitalised, so `sparkth_user` reads "Sparkth user".
 */
export function formatRoleName(name: string): string {
  const spaced = name.replace(/_+/g, " ").trim();
  return spaced.charAt(0).toLocaleUpperCase() + spaced.slice(1);
}
