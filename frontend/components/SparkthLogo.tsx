import Image from "next/image";

export function SparkthLogo({ size = 80 }: { size?: number }) {
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
