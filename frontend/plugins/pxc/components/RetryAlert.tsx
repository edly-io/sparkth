"use client";

import { useTranslations } from "next-intl";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";

// An error alert for a failure that a retry can fix, with the button that runs it.
export function RetryAlert({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}): React.JSX.Element {
  const t = useTranslations("pxc");
  return (
    <Alert severity="error">
      <div className="flex items-center justify-between gap-3">
        <span>{message}</span>
        <Button variant="ghost" size="sm" onClick={onRetry}>
          {t("retry")}
        </Button>
      </div>
    </Alert>
  );
}
