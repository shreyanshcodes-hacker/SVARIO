import type { Metadata } from "next";
import "./globals.css";
import { SVARIO_BRAND } from "@/config/brand";
import { AuthOrganizationProvider } from "@/context/AuthOrganizationContext";

export const metadata: Metadata = {
  title: `${SVARIO_BRAND.name} — ${SVARIO_BRAND.tagline}`,
  description: SVARIO_BRAND.description,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.JSX.Element {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0B1020] text-[#F5F7FC] selection:bg-[#7657F6] selection:text-[#F5F7FC]">
        <AuthOrganizationProvider>{children}</AuthOrganizationProvider>
      </body>
    </html>
  );
}
