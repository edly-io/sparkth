import { useId, useState } from "react";
import { useTranslations } from "next-intl";

interface OptionsPromptProps {
  options: string[];
  single: boolean;
  interactive: boolean;
  selected: string[];
  answered: boolean;
  onOptionCheck: (option: string, previous?: string) => void;
}

/** `checked` with `option` added, or removed if it was already there. */
function toggleOption(checked: string[], option: string): string[] {
  return checked.includes(option) ? checked.filter((o) => o !== option) : [...checked, option];
}

/**
 * The checked options after `option` is picked, reporting a newly checked one to `onOptionCheck`.
 * A `single` pick replaces the current choice (passed as `previous`); otherwise it toggles.
 */
function pickOption(
  checked: string[],
  option: string,
  single: boolean,
  onOptionCheck: OptionsPromptProps["onOptionCheck"],
): string[] {
  if (single) {
    if (!checked.includes(option)) onOptionCheck(option, checked[0]);
    return [option];
  }
  if (!checked.includes(option)) onOptionCheck(option);
  return toggleOption(checked, option);
}

/**
 * Checkboxes for the options an assistant question offers, or radio buttons when the question
 * takes a `single` answer. While `interactive`, picking an option hands it to `onOptionCheck`
 * (the message box collects it; a radio pick also passes the option it replaces) and a note points
 * to the message box for anything else. Otherwise the inputs are disabled with `selected` checked,
 * and an `answered` question that matched no option says so.
 */
export function OptionsPrompt({
  options,
  single,
  interactive,
  selected,
  answered,
  onOptionCheck,
}: OptionsPromptProps) {
  const t = useTranslations("compose");
  const groupName = useId();
  const [checked, setChecked] = useState<string[]>([]);
  const shown = interactive ? checked : selected;

  return (
    <div className="mt-4 space-y-3">
      <ul className="space-y-1.5">
        {options.map((option) => (
          <li key={option}>
            <label className="flex items-center gap-2 text-sm">
              <input
                type={single ? "radio" : "checkbox"}
                name={groupName}
                checked={shown.includes(option)}
                disabled={!interactive}
                onChange={() => setChecked(pickOption(checked, option, single, onOptionCheck))}
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
