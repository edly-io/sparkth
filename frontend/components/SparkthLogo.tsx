import Image from "next/image";

interface SparkthLogoProps {
  size?: number;
  iconOnly?: boolean;
}

export function SparkthLogo({ size = 80, iconOnly = false }: SparkthLogoProps) {
  if (iconOnly) {
    return (
      <Image
        src="/icon.png"
        alt="Sparkth"
        width={size}
        height={size}
        className="rounded-lg"
        unoptimized
      />
    );
  }

  return (
    <div className="inline-block">
      <div className="flex items-center gap-2">
        <div className="relative inline-block">
          <Image
            src="/compose-logo.png"
            alt="Compose"
            width={140}
            height={40}
            style={{ height: size, width: "auto" }}
            unoptimized
          />
        </div>
      </div>
    </div>
  );
}
