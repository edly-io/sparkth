import { useState, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

interface OptionsPromptProps {
  options: string[];
  interactive: boolean;
  onRespond: (text: string) => void;
}

/** `checked` with `option` added, or removed if it was already there. */
function toggleOption(checked: string[], option: string): string[] {
  return checked.includes(option) ? checked.filter((o) => o !== option) : [...checked, option];
}

/** The reply text: checked options in display order, then the trimmed free text, one per line. */
function buildReply(options: string[], checked: string[], other: string): string {
  return [...options.filter((option) => checked.includes(option)), other.trim()]
    .filter(Boolean)
    .join("\n");
}

/**
 * Checkboxes for the options an assistant question offers, a free-text input for anything else,
 * and a Respond button. Read-only (disabled, unchecked, no input or button) unless `interactive`.
 */
export function OptionsPrompt({ options, interactive, onRespond }: OptionsPromptProps) {
  const t = useTranslations("chat");
  const [checked, setChecked] = useState<string[]>([]);
  const [other, setOther] = useState("");
  // ponytail: locks after one send; a send the AI-key guard refuses leaves the widget locked,
  // and the author answers in the compose box instead. Unlock on refusal if that proves common.
  const [sent, setSent] = useState(false);
  const reply = buildReply(options, checked, other);
  const canRespond = interactive && !sent && reply !== "";

  const respond = () => {
    if (!canRespond) return;
    setSent(true);
    onRespond(reply);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    respond();
  };

  return (
    <div className="mt-4 space-y-3">
      <ul className="space-y-1.5">
        {options.map((option) => (
          <li key={option}>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={interactive && checked.includes(option)}
                disabled={!interactive || sent}
                onChange={() => setChecked((prev) => toggleOption(prev, option))}
              />
              {option}
            </label>
          </li>
        ))}
      </ul>
      {interactive && (
        <div className="flex items-center gap-2">
          <Input
            value={other}
            onChange={(event) => setOther(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t("optionsOtherPlaceholder")}
            aria-label={t("optionsOtherPlaceholder")}
            disabled={sent}
            className="py-2"
          />
          <Button size="sm" disabled={!canRespond} onClick={respond}>
            {t("optionsRespond")}
          </Button>
        </div>
      )}
    </div>
  );
}
