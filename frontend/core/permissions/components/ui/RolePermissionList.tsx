"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import { twMerge } from "tailwind-merge";
import { Input } from "@/core/components/ui/Input";
import { RiskChips } from "@/core/permissions/components/ui/RiskChips";
import { filterPermissions, groupByCategory } from "@/core/permissions/permissionList";
import type { PermissionResponse } from "@/core/permissions/types";

/**
 * Every permission, grouped under its category, with those in `granted` ticked: each shows its label,
 * risks, description and internal name, and each group how many of its permissions are granted. A
 * group can be collapsed, and a filter narrows the list by label, category or internal name. With
 * `onChange`, permissions can be ticked and unticked, one at a time or a whole category at once, and
 * each change hands over the permissions granted after it; without it, none can be changed. `actions`
 * sit beside the filter.
 */
export function RolePermissionList({
  permissions,
  granted,
  onChange,
  actions,
}: {
  permissions: PermissionResponse[];
  granted: ReadonlySet<string>;
  onChange?: (granted: ReadonlySet<string>) => void;
  actions?: ReactNode;
}) {
  const t = useTranslations("permissions.roles.detail.list");
  const tPermissions = useTranslations("permissions");
  const [filter, setFilter] = useState("");
  const [collapsedCategories, setCollapsedCategories] = useState<ReadonlySet<string>>(new Set());
  const byCategory = groupByCategory(permissions);
  const matchingByCategory = groupByCategory(filterPermissions(permissions, filter));
  const grantedCount = permissions.filter(({ name }) => granted.has(name)).length;

  const toggleGranted = (permission: string) => {
    const next = new Set(granted);
    if (!next.delete(permission)) next.add(permission);
    onChange?.(next);
  };

  // Grants every permission in the category, or clears them all when every one is granted.
  const toggleCategoryGranted = (categoryPermissions: PermissionResponse[]) => {
    const grantAll = !categoryPermissions.every(({ name }) => granted.has(name));
    const next = new Set(granted);
    for (const { name } of categoryPermissions) {
      if (grantAll) next.add(name);
      else next.delete(name);
    }
    onChange?.(next);
  };

  const toggleCollapsed = (category: string) => {
    const next = new Set(collapsedCategories);
    if (!next.delete(category)) next.add(category);
    setCollapsedCategories(next);
  };

  return (
    <section aria-label={t("label")} className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="w-full max-w-xs">
          <Input
            type="search"
            aria-label={t("filter")}
            placeholder={t("filter")}
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            className="border px-3 py-1.5 text-sm"
          />
        </div>
        <p className="text-sm text-muted-foreground">
          {t.rich("granted", {
            granted: grantedCount,
            total: permissions.length,
            strong: (chunks) => <strong className="font-semibold text-foreground">{chunks}</strong>,
          })}
        </p>
        {actions && <div className="ml-auto flex items-center gap-3">{actions}</div>}
      </div>
      {matchingByCategory.size === 0 && (
        <p className="text-sm text-muted-foreground">{tPermissions("picker.noMatches")}</p>
      )}
      {[...matchingByCategory].map(([category, categoryMatches]) => {
        const open = !collapsedCategories.has(category);
        const categoryPermissions = byCategory.get(category) ?? [];
        const categoryGrantedCount = categoryPermissions.filter(({ name }) =>
          granted.has(name),
        ).length;
        const allGranted = categoryGrantedCount === categoryPermissions.length;
        return (
          <fieldset
            key={category}
            className="overflow-hidden rounded-xl border border-border bg-card"
          >
            <legend className="sr-only">{category}</legend>
            <div className="flex items-center gap-3 bg-surface-variant px-4">
              <input
                type="checkbox"
                aria-label={t("allInCategory", { category })}
                className="h-4 w-4 shrink-0 accent-primary-600"
                checked={allGranted}
                ref={(box) => {
                  if (box) box.indeterminate = categoryGrantedCount > 0 && !allGranted;
                }}
                disabled={!onChange}
                onChange={() => toggleCategoryGranted(categoryPermissions)}
              />
              <button
                type="button"
                aria-expanded={open}
                onClick={() => toggleCollapsed(category)}
                className="flex flex-1 items-center gap-2.5 py-3 text-left"
              >
                <span className="text-[15px] font-semibold text-foreground">{category}</span>
                <span className="text-[13px] text-muted-foreground">
                  {t("groupCount", {
                    granted: categoryGrantedCount,
                    total: categoryPermissions.length,
                  })}
                </span>
                <ChevronDown
                  className={twMerge(
                    "ml-auto h-4 w-4 text-muted-foreground transition-transform",
                    open && "rotate-180",
                  )}
                  aria-hidden="true"
                />
              </button>
            </div>
            {open && (
              <ul className="divide-y divide-border border-t border-border">
                {categoryMatches.map(({ name, label, description, risks }) => (
                  <li key={name} className="flex gap-3 px-4 py-3">
                    <input
                      id={`permission-${name}`}
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 shrink-0 accent-primary-600"
                      checked={granted.has(name)}
                      disabled={!onChange}
                      onChange={() => toggleGranted(name)}
                    />
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <label
                          htmlFor={`permission-${name}`}
                          className="text-sm font-medium text-foreground"
                        >
                          {label}
                        </label>
                        <RiskChips risks={risks} />
                      </div>
                      <p className="text-sm text-muted-foreground">{description}</p>
                      <code className="text-xs text-muted-foreground">{name}</code>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>
        );
      })}
    </section>
  );
}
