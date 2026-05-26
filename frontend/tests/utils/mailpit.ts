import type { APIRequestContext } from "@playwright/test";
import { mailpitBaseUrl } from "../config";

/**
 * Mailpit helpers — Sparkth's local dev SMTP catcher.
 *
 * Mailpit exposes a JSON API on `MP_HTTP_PORT` (8025 by default). The
 * `compose.yml` service `mailpit` accepts mail from the API at port 1025 and
 * we read it back via the HTTP API.
 *
 * Reference: https://github.com/axllent/mailpit/wiki/API-v1
 */

interface MailpitMessage {
  ID: string;
  To: { Address: string; Name: string }[];
  From: { Address: string; Name: string };
  Subject: string;
  Created: string;
}

interface MailpitListResponse {
  messages: MailpitMessage[];
  total: number;
}

interface MailpitMessageDetail {
  ID: string;
  Subject: string;
  Text: string;
  HTML: string;
}

/**
 * Find the most recent message sent to `recipient`. Polls up to `timeoutMs`
 * since the SMTP delivery is asynchronous from the user-facing register call.
 */
export async function findLatestMessageTo(
  request: APIRequestContext,
  recipient: string,
  timeoutMs = 10_000,
): Promise<MailpitMessageDetail> {
  const deadline = Date.now() + timeoutMs;
  let lastError = "no messages received";

  while (Date.now() < deadline) {
    const listResponse = await request.get(
      `${mailpitBaseUrl}/api/v1/search?query=${encodeURIComponent(`to:${recipient}`)}`,
    );

    if (listResponse.ok()) {
      const list = (await listResponse.json()) as MailpitListResponse;
      if (list.messages.length > 0) {
        const messageId = list.messages[0].ID;
        const detailResponse = await request.get(`${mailpitBaseUrl}/api/v1/message/${messageId}`);
        if (detailResponse.ok()) {
          return (await detailResponse.json()) as MailpitMessageDetail;
        }
        lastError = `failed to fetch message ${messageId}: ${detailResponse.status()}`;
      }
    } else {
      lastError = `mailpit search failed: ${listResponse.status()}`;
    }

    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`Timed out waiting for email to ${recipient}: ${lastError}`);
}

/**
 * Extract the verification link from a message body (text or HTML).
 *
 * Anchored on `/verify-email` (the actual route in `app/services/email_verification.py`)
 * so that future template changes — branded logos, footer social links, etc. —
 * don't cause us to capture the wrong URL. The trailing character class only
 * excludes whitespace/quotes/angle-brackets so `?`, `&`, `=` in the query
 * string are preserved.
 */
export function extractVerificationLink(message: MailpitMessageDetail): string {
  const haystack = message.Text || message.HTML;
  const match = haystack.match(/https?:\/\/[^\s"<>]*\/verify-email[^\s"<>]*/);
  if (!match) {
    throw new Error(
      `No verify-email link found in message ${message.ID} (subject: ${message.Subject})`,
    );
  }
  // Trim a single trailing prose-punctuation char that the email body may have
  // (e.g., a period at the end of a sentence in the HTML preview).
  return match[0].replace(/[.,;:!)]$/, "");
}
