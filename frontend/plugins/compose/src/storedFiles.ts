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

// Writes `value` under `key`, and returns whether it was written. While storage is full, other
// conversations give up their files, those added longest ago first.
function saveToStorage(key: string, value: string): boolean {
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

/**
 * Adds files to the ones this browser keeps for a conversation.
 *
 * When storage is full, other conversations give up their files, those added longest ago first.
 * When the files still don't fit, or storage is blocked, they aren't kept.
 */
export function addStoredFiles(userId: number, conversationId: string, files: StoredFile[]): void {
  const entry: StoredEntry = {
    updatedAt: Date.now(),
    files: [...getStoredFiles(userId, conversationId), ...files],
  };
  saveToStorage(getKey(userId, conversationId), JSON.stringify(entry));
}

const LIMIT_CHECK_KEY = `${KEY_PREFIX}limit-check`;

/**
 * Whether a file's text fits within this browser's storage limit, checked by writing it and removing it
 * again. Other conversations may give up their files to make it fit.
 */
export function isWithinStorageLimit(text: string): boolean {
  const isWithin = saveToStorage(LIMIT_CHECK_KEY, text);
  if (isWithin) localStorage.removeItem(LIMIT_CHECK_KEY);
  return isWithin;
}
