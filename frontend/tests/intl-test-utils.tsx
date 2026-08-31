import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import en from "@/messages/en.json";
import type { Messages } from "@/lib/i18n/messages";

// Renders inside NextIntlClientProvider with the English catalog, so component
// tests keep matching on English text. A plugin component test passes its
// plugin's English catalog as `extraMessages`.
export function renderWithIntl(ui: React.ReactElement, extraMessages?: Partial<Messages>) {
  return render(
    <NextIntlClientProvider locale="en" messages={{ ...en, ...extraMessages }}>
      {ui}
    </NextIntlClientProvider>,
  );
}
