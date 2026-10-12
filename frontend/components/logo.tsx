import Link from "next/link";

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2.5 font-semibold tracking-[-0.04em] text-ink">
      <span className="relative grid size-7 place-items-center rounded-full bg-blue-600 text-white">
        <span className="absolute h-3.5 w-[2px] rotate-45 rounded-full bg-white" />
        <span className="absolute h-3.5 w-[2px] -rotate-45 rounded-full bg-white/70" />
      </span>
      <span className="text-[1.45rem]">spectre</span>
    </Link>
  );
}
