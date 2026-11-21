/** A file uploaded from the computer, as this browser keeps it for its conversation. */
export interface StoredFile {
  name: string;
  size: number;
  text: string;
}

interface StoredEntry {
  updatedAt: number;
  files: StoredFile[];
}

const KEY_PREFIX = "compose.files.";

function getKey(userId: number, conversationId: string): string {
  return `${KEY_PREFIX}${userId}.${conversationId}`;
}

/** The files this browser keeps for a conversation; none when storage is blocked or unreadable. */
export function getStoredFiles(userId: number, conversationId: string): StoredFile[] {
  try {
    const raw = localStorage.getItem(getKey(userId, conversationId));
    return raw ? (JSON.parse(raw) as StoredEntry).files : [];
  } catch (error) {
    console.warn("Could not read the conversation's files from this browser:", error);
    return [];
  }
}

// Gives up the files of the conversation whose files were added longest ago, other than `keptKey`'s.
// Returns false when there is none.
function removeOldestEntry(keptKey: string): boolean {
  let oldestKey: string | null = null;
  let oldestUpdatedAt = Infinity;
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key?.startsWith(KEY_PREFIX) || key === keptKey) continue;
    let updatedAt = 0;
    try {
      updatedAt = (JSON.parse(localStorage.getItem(key) ?? "") as StoredEntry).updatedAt;
    } catch {
      // An unreadable entry goes first.
    }
    if (updatedAt < oldestUpdatedAt) {
      oldestKey = key;
      oldestUpdatedAt = updatedAt;
    }
  }
  if (oldestKey === null) return false;
  localStorage.removeItem(oldestKey);
  return true;
}

/**
 * Adds files to the ones this browser keeps for a conversation, and returns whether they were kept.
 *
 * When storage is full, other conversations give up their files, those added longest ago first.
 * When the files still don't fit, or storage is blocked, they aren't kept.
 */
export function addStoredFiles(
  userId: number,
  conversationId: string,
  files: StoredFile[],
): boolean {
  const key = getKey(userId, conversationId);
  const entry: StoredEntry = {
    updatedAt: Date.now(),
    files: [...getStoredFiles(userId, conversationId), ...files],
  };
  const value = JSON.stringify(entry);
  for (;;) {
    try {
      localStorage.setItem(key, value);
      return true;
    } catch (error) {
      const isFull = error instanceof DOMException && error.name === "QuotaExceededError";
      if (!isFull || !removeOldestEntry(key)) {
        console.warn("Could not keep the conversation's files in this browser:", error);
        return false;
      }
    }
  }
}
