import Link from "next/link";
import type { ComponentType } from "react";

interface NavItemProps {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  isActive: boolean;
  isCollapsed?: boolean;
  onClick?: () => void;
}

export function NavItem({
  href,
  label,
  icon: Icon,
  isActive,
  isCollapsed = false,
  onClick,
}: NavItemProps) {
  return (
    <div>
      <Link
        href={href}
        onClick={onClick}
        className={`
          flex items-center gap-3 px-3 py-2 min-h-[40px] rounded-lg transition-colors
          ${isCollapsed ? "justify-center" : ""}
          ${
            isActive
              ? "bg-primary-500/15 text-primary-600 dark:text-primary-400 border-l-3 border-primary-500"
              : "text-foreground hover:bg-surface-variant"
          }
        `}
        title={isCollapsed ? label : undefined}
      >
        <Icon className="w-5 h-5 flex-shrink-0" />
        {!isCollapsed && <span className="font-medium">{label}</span>}
      </Link>
    </div>
  );
}
