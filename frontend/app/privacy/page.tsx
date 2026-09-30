// Written with the assistance of an LLM (Claude).
import type { Metadata } from "next";
import Link from "next/link";

const CONTACT_EMAIL = "support@edly.io";
const LAST_UPDATED = "September 30, 2026";

export const metadata: Metadata = {
  title: "Privacy Policy — Sparkth",
  description: "How Sparkth collects, uses, stores, shares and deletes your data.",
};

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="max-w-3xl mx-auto py-12 px-4 sm:px-6 lg:px-8 space-y-8 leading-relaxed">
        <header className="space-y-2">
          <Link href="/" className="text-primary-500 hover:underline">
            ← Sparkth
          </Link>
          <h1 className="text-3xl font-extrabold">Privacy Policy</h1>
          <p className="text-muted-foreground">Last updated: {LAST_UPDATED}</p>
        </header>

        <p>
          Sparkth is an AI-powered platform for creating educational content, operated by Edly. This
          policy explains what data Sparkth collects, including data received from Google APIs, how
          it is used, where it is stored, who it is shared with, and how you can delete it.
        </p>

        <section className="space-y-3">
          <h2 className="text-xl font-bold">1. Google data we access</h2>
          <p>
            <strong>Google Sign-In.</strong> When you sign in with Google, Sparkth receives your
            basic profile information. We store your name, email address and Google account ID. We
            do not store your profile picture or your Google sign-in tokens.
          </p>
          <p>
            <strong>Google Drive.</strong> If you choose to connect Google Drive, Sparkth asks for
            read access to your Drive, access to the files it creates for you, and the email address
            of the connected account. Sparkth accesses:
          </p>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              Metadata of the files and folders you browse, search or add: name, ID, parent folder,
              MIME type, size, checksum and modified time.
            </li>
            <li>
              The content of the files you add to Sparkth. Google Docs, Sheets and Slides are
              exported as PDF to read their content.
            </li>
            <li>
              The email address of the connected Drive account, shown to you on the connection
              status screen.
            </li>
          </ul>
          <p>
            Sparkth writes to your Drive only when you ask it to: creating folders, uploading files
            and renaming files. Sparkth never deletes files from your Drive.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-bold">2. How we use it</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              Your name, email and Google account ID are used to create your account and log you in.
            </li>
            <li>
              Drive metadata is used to let you browse, search and pick the files and folders you
              want to use in Sparkth.
            </li>
            <li>
              Drive file content is converted to text and used as source material when you generate
              course content or chat with the AI assistant.
            </li>
            <li>
              Drive write access is used to save files and folders you create or export from
              Sparkth.
            </li>
          </ul>
          <p>We do not use Google user data for advertising, and we do not sell it.</p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-bold">3. Where it is stored and how it is protected</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              Account details, Drive file metadata and the text extracted from your Drive files are
              stored in Sparkth&apos;s database.
            </li>
            <li>Downloaded file bytes are processed in memory and are not written to disk.</li>
            <li>Google Drive access and refresh tokens are encrypted at rest.</li>
            <li>AI provider API keys you add are encrypted at rest.</li>
            <li>Passwords are stored only as salted hashes.</li>
            <li>
              Every request is authenticated, and your Drive data is only accessible to your own
              account. Data is sent over encrypted HTTPS connections.
            </li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-bold">4. Who we share it with</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>AI providers.</strong> When you use AI features, relevant excerpts of your
              Drive file content and your messages are sent to the AI provider you configure in
              Sparkth (OpenAI, Anthropic or Google Gemini), using the API key you provide. The
              provider processes this data under its own API terms.
            </li>
            <li>
              <strong>Email delivery.</strong> Your email address is sent to our email server to
              deliver verification emails.
            </li>
          </ul>
          <p>We do not share Google user data with any other third party.</p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-bold">5. Retention and deletion</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>We keep your data while your account is active.</li>
            <li>
              Removing a file or folder in Sparkth stops it from being used in AI features.
              Disconnecting Google Drive in Sparkth revokes Sparkth&apos;s access token with Google.
            </li>
            <li>
              You can also revoke Sparkth&apos;s access at any time from your{" "}
              <a
                href="https://myaccount.google.com/permissions"
                className="text-primary-500 hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Google Account permissions
              </a>{" "}
              page.
            </li>
            <li>
              To delete your account and all associated data, including stored Google data, email us
              at{" "}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary-500 hover:underline">
                {CONTACT_EMAIL}
              </a>
              . We will process your request promptly and complete the deletion within 30 days.
            </li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-bold">6. Google API Limited Use</h2>
          <p>
            {
              "Sparkth's use and transfer of information received from Google APIs will adhere to the Google API Services User Data Policy, including the Limited Use requirements."
            }
          </p>
          <p>
            See the{" "}
            <a
              href="https://developers.google.com/terms/api-services-user-data-policy"
              className="text-primary-500 hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              Google API Services User Data Policy
            </a>
            .
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-bold">7. AI and machine learning</h2>
          <p>
            Sparkth does not use Google Workspace data to develop, improve, or train generalized AI
            or machine learning models.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-bold">8. Contact</h2>
          <p>
            For privacy questions or deletion requests, contact Edly at{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary-500 hover:underline">
              {CONTACT_EMAIL}
            </a>
            .
          </p>
        </section>
      </main>
    </div>
  );
}
