"use client";

import type { ReactElement } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/Tooltip";

interface ActionTooltipProps {
  label: string;
  children: ReactElement;
}

/** Shows `label` beside an icon-only history action on hover or focus. */
export function ActionTooltip({ label, children }: ActionTooltipProps): ReactElement {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="right" sideOffset={8}>
        {label}
      </TooltipContent>
    </Tooltip>
  );
}
