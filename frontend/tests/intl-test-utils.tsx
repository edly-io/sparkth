import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import en from "@/messages/en.json";

// Renders a component inside NextIntlClientProvider with the English catalog, so
// component tests can keep matching on English text while the component itself
// reads it through useTranslations.
export function renderWithIntl(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      {ui}
    </NextIntlClientProvider>,
  );
}
