import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement, ReactNode } from "react";

import en from "@/messages/en.json";
import type { Messages } from "@/lib/i18n/messages";

/** The provider's props: the English core catalog merged with `messages`, in UTC. */
function intlProps(messages?: Partial<Messages>) {
  return { locale: "en", timeZone: "UTC", messages: { ...en, ...messages } } as const;
}

/**
 * Provides translations the way the app does, for a component test: the English core catalog
 * merged with `messages` (a plugin's English catalog), in UTC, so tests match on English text and
 * fixed dates.
 */
export function IntlTestProvider({
  messages,
  children,
}: {
  messages?: Partial<Messages>;
  children: ReactNode;
}) {
  return <NextIntlClientProvider {...intlProps(messages)}>{children}</NextIntlClientProvider>;
}

/**
 * Renders `ui` with the same translations as {@link IntlTestProvider}; a plugin's test passes its
 * English catalog. The provider is rendered directly, not through that component, so a test that
 * re-renders under a bare `NextIntlClientProvider` keeps the component mounted.
 */
export function renderWithIntl(ui: ReactElement, messages?: Partial<Messages>) {
  return render(<NextIntlClientProvider {...intlProps(messages)}>{ui}</NextIntlClientProvider>);
}
