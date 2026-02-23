export async function loadPrompt(path: string): Promise<string> {
  const res = await fetch(path);

  if (!res.ok) {
    throw new Error(`Failed to load prompt: ${path}`);
  }

  return res.text();
}
