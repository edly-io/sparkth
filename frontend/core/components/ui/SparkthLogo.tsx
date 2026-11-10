import Image from "next/image";

interface SparkthLogoProps {
  size?: number;
  iconOnly?: boolean;
}

export function SparkthLogo({ size = 80, iconOnly = false }: SparkthLogoProps) {
  const iconSize = iconOnly ? size : size * 0.72;
  const composeFontSize = size * 0.62;
  const subtitleFontSize = size * 0.16;

  return (
    <div
      className="inline-grid items-center leading-none select-none"
      style={{
        gridTemplateColumns: iconOnly ? "auto 0fr" : "auto 1fr",
        columnGap: iconOnly ? 0 : `${size * 0.06}px`,
        transition: "grid-template-columns 300ms ease, column-gap 300ms ease",
      }}
    >
      <Image
        src="/icon.png"
        alt="Sparkth"
        width={160}
        height={160}
        className="rounded-lg"
        style={{ width: iconSize, height: iconSize }}
        unoptimized
      />
      <div
        className="flex flex-col items-center overflow-hidden min-w-0"
        style={{ opacity: iconOnly ? 0 : 1, transition: "opacity 300ms ease" }}
        aria-hidden={iconOnly}
      >
        <span
          className="font-extrabold text-primary-500 whitespace-nowrap"
          style={{ fontSize: composeFontSize, lineHeight: 1 }}
        >
          compose
        </span>
        <span
          className="font-medium text-neutral-500 dark:text-white whitespace-nowrap"
          style={{
            fontSize: subtitleFontSize,
            letterSpacing: `${subtitleFontSize * 0.45}px`,
            lineHeight: 1,
            marginTop: size * 0.05,
          }}
        >
          powered by Edly
        </span>
      </div>
    </div>
  );
}
