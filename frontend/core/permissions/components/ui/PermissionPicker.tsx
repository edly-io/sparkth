"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Input } from "@/core/components/ui/Input";
import { RiskChips } from "@/core/permissions/components/ui/RiskChips";
import type { PermissionResponse } from "@/core/permissions/types";

/**
 * Every permission as a checkbox labelled in plain words and tagged with its risks, grouped under its
 * category in the order given. A search box narrows the list by label or category; the count of chosen
 * permissions includes any the search hides. Ticking or unticking one calls `onToggle` with its name.
 */
export function PermissionPicker({
  permissions,
  chosen,
  onToggle,
}: {
  permissions: PermissionResponse[];
  chosen: ReadonlySet<string>;
  onToggle: (name: string) => void;
}) {
  const t = useTranslations("permissions.roles.create.picker");
  const tPermissions = useTranslations("permissions");
  const [search, setSearch] = useState("");
  const query = search.trim().toLocaleLowerCase();
  const shown = permissions.filter(
    ({ label, category }) =>
      label.toLocaleLowerCase().includes(query) || category.toLocaleLowerCase().includes(query),
  );
  const categories = [...new Set(shown.map(({ category }) => category))];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <Input
          id="permission-search"
          type="search"
          aria-label={t("search")}
          placeholder={t("search")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="border px-3 py-1.5 text-sm"
        />
        <span className="shrink-0 text-sm text-muted-foreground">
          {t("chosen", { count: chosen.size })}
        </span>
      </div>
      <div className="max-h-34 space-y-3 overflow-y-auto rounded-lg border border-border px-3 py-2">
        {categories.length === 0 && (
          <p className="text-sm text-muted-foreground">{tPermissions("noPermissionsMatch")}</p>
        )}
        {categories.map((category) => (
          <fieldset key={category}>
            <legend className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {category}
            </legend>
            <ul className="space-y-1.5">
              {shown
                .filter((permission) => permission.category === category)
                .map(({ name, label, risks }) => (
                  <li key={name} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <label className="flex items-center gap-2 text-sm text-foreground">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-primary-600"
                        checked={chosen.has(name)}
                        onChange={() => onToggle(name)}
                      />
                      {label}
                    </label>
                    <RiskChips risks={risks} />
                  </li>
                ))}
            </ul>
          </fieldset>
        ))}
      </div>
    </div>
  );
}
