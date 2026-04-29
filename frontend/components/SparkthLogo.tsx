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
      className="inline-flex items-center leading-none select-none"
      style={{
        gap: iconOnly ? 0 : size * 0.06,
        transition: "gap 300ms ease",
      }}
    >
      <Image
        src="/icon.png"
        alt="Sparkth"
        width={160}
        height={160}
        className="rounded-lg"
        style={{
          width: iconSize,
          height: iconSize,
          transition: "width 300ms ease, height 300ms ease",
        }}
        unoptimized
      />
      <div
        className="flex flex-col items-center overflow-hidden"
        style={{
          maxWidth: iconOnly ? 0 : size * 5,
          opacity: iconOnly ? 0 : 1,
          transition: "max-width 300ms ease, opacity 300ms ease",
        }}
        aria-hidden={iconOnly}
      >
        <span
          className="font-extrabold text-primary-500 whitespace-nowrap"
          style={{
            fontSize: composeFontSize,
            lineHeight: 1,
            transition: "font-size 300ms ease",
          }}
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
            transition: "font-size 300ms ease, letter-spacing 300ms ease, margin-top 300ms ease",
          }}
        >
          powered by Edly
        </span>
      </div>
    </div>
  );
}
