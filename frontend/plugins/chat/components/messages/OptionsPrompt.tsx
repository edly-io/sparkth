import { useState } from "react";
import { useTranslations } from "next-intl";

interface OptionsPromptProps {
  options: string[];
  interactive: boolean;
  selected: string[];
  answered: boolean;
  onOptionCheck: (option: string) => void;
}

/** `checked` with `option` added, or removed if it was already there. */
function toggleOption(checked: string[], option: string): string[] {
  return checked.includes(option) ? checked.filter((o) => o !== option) : [...checked, option];
}

/**
 * Checkboxes for the options an assistant question offers. While `interactive`, checking a box
 * hands its option to `onOptionCheck` (the message box collects it) and a note points to the
 * message box for anything else. Otherwise the boxes are disabled with `selected` checked, and an
 * `answered` question that matched no option says so.
 */
export function OptionsPrompt({
  options,
  interactive,
  selected,
  answered,
  onOptionCheck,
}: OptionsPromptProps) {
  const t = useTranslations("chat");
  const [checked, setChecked] = useState<string[]>([]);
  const shown = interactive ? checked : selected;

  return (
    <div className="mt-4 space-y-3">
      <ul className="space-y-1.5">
        {options.map((option) => (
          <li key={option}>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={shown.includes(option)}
                disabled={!interactive}
                onChange={() => {
                  if (!checked.includes(option)) onOptionCheck(option);
                  setChecked((prev) => toggleOption(prev, option));
                }}
              />
              {option}
            </label>
          </li>
        ))}
      </ul>
      {interactive && <p className="text-xs text-muted-foreground">{t("optionsTypeElse")}</p>}
      {answered && selected.length === 0 && (
        <p className="text-xs text-muted-foreground">{t("optionsNoneSelected")}</p>
      )}
    </div>
  );
}
