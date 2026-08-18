"use client";

import { NextIntlClientProvider } from "next-intl";
import { useEffect, useState } from "react";

import { readLocaleCookie, type Locale } from "@/lib/i18n/config";
import { loadMessages, type Messages } from "@/lib/i18n/messages";

// Resolves the UI locale on the client (production is a static export, so there
// is no server to negotiate it) and provides the matching message catalog.
// Renders nothing until the catalog is loaded, so no untranslated flash occurs.
export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<{ locale: Locale; messages: Messages } | null>(null);

  useEffect(() => {
    const locale = readLocaleCookie();
    let cancelled = false;
    loadMessages(locale).then((messages) => {
      if (cancelled) return;
      document.documentElement.lang = locale;
      setState({ locale, messages });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === null) return null;
  return (
    <NextIntlClientProvider locale={state.locale} messages={state.messages}>
      {children}
    </NextIntlClientProvider>
  );
}
