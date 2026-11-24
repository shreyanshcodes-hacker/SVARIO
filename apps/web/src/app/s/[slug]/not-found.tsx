import React from "react";
import Link from "next/link";

export default function PublicSalonNotFoundPage(): React.JSX.Element {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#0B1020] px-6 text-center text-[#F5F7FC]">
      <div className="max-w-md space-y-4 rounded-3xl border border-white/10 bg-[#171D33]/90 p-8 shadow-2xl">
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-[#36C6D3]">404 · Unavailable</p>
        <h1 className="text-2xl font-bold text-white">Booking Website Not Found</h1>
        <p className="text-sm leading-relaxed text-[#A7B0C4]">
          This salon booking link does not exist or is not currently published. Please check the URL
          with your salon and try again.
        </p>
        <div className="pt-2">
          <Link
            href="/"
            className="inline-block rounded-xl bg-[#7657F6] px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-[#6546e6]"
          >
            Return to Svario
          </Link>
        </div>
      </div>
    </main>
  );
}
