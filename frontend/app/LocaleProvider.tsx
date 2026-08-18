"use client";

import { NextIntlClientProvider } from "next-intl";
import { useEffect, useState } from "react";

import en from "@/messages/en.json";
import { defaultLocale, readLocaleCookie, type Locale } from "@/lib/i18n/config";
import { loadMessages, type Messages } from "@/lib/i18n/messages";

// Production is a static export, so the locale is resolved client-side from the
// cookie. Rendering starts synchronously on the bundled English catalog (keeping
// the prerendered HTML non-empty) and swaps to the cookie locale once its catalog
// chunk loads; a failed load logs and stays on English.
export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<{ locale: Locale; messages: Messages }>({
    locale: defaultLocale,
    messages: en,
  });

  useEffect(() => {
    const locale = readLocaleCookie();
    if (locale === defaultLocale) return;
    let cancelled = false;
    loadMessages(locale)
      .then((messages) => {
        if (cancelled) return;
        document.documentElement.lang = locale;
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
