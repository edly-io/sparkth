import Image from "next/image";

export function SparkthLogo() {
  return (
    <div className="px-4 py-6">
      <div className="inline-block">
        <div className="flex items-center gap-2">
          <div className="relative inline-block">
            <Image
              src="/sparkth-logo.png"
              alt="Sparkth"
              width={140}
              height={40}
              className="h-10 w-auto"
              unoptimized
            />
          </div>
        </div>
      </div>
    </div>
  );
}
