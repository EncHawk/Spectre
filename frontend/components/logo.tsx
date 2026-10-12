import Image from "next/image";
import Link from "next/link";

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} aria-label="Spectre home" className="inline-flex items-center gap-2.5 font-semibold tracking-[-0.04em] text-ink">
      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-white p-1 shadow-sm ring-1 ring-black/10">
        <Image src="/images/spectre-logo.png" alt="" width={36} height={38} priority className="h-full w-full object-contain" />
      </span>
      <span className="text-[1.45rem]">spectre</span>
    </Link>
  );
}
