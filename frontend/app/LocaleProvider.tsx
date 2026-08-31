"use client";

import { NextIntlClientProvider } from "next-intl";
import { useEffect, useState } from "react";

import en from "@/messages/en.json";
import { setActiveLocale } from "@/lib/i18n/active-locale";
import { defaultLocale, readLocaleCookie, type Locale } from "@/lib/i18n/config";
import { loadMessages, type LoadedMessages } from "@/lib/i18n/messages";

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<{ locale: Locale; messages: LoadedMessages }>({
    locale: defaultLocale,
    messages: en,
  });

  useEffect(() => {
    // Runs for the default locale too: the synchronous seed above carries only
    // the core catalog, and plugin catalogs arrive through this load.
    const locale = readLocaleCookie();
    let cancelled = false;
    loadMessages(locale)
      .then((messages) => {
        if (cancelled) return;
        document.documentElement.lang = locale;
        setActiveLocale(locale);
        setState({ locale, messages });
      })
      .catch((error: unknown) => {
        console.error(`i18n: failed to load the "${locale}" catalog, staying on English`, error);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <NextIntlClientProvider locale={state.locale} messages={state.messages}>
      {children}
    </NextIntlClientProvider>
  );
}
