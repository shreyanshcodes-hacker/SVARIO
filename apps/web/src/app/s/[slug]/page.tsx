import React from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PublicBookingWebsiteRenderer } from "@/components/booking-website/PublicBookingWebsiteRenderer";
import { fetchPublicBookingWebsite } from "@/lib/api";

export const dynamic = "force-dynamic";

interface PublicSalonPageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({
  params,
}: PublicSalonPageProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const website = await fetchPublicBookingWebsite(slug);
    if (!website) {
      return {
        title: "Salon Not Found — Svario",
        robots: { index: false, follow: false },
      };
    }
    return {
      title: `${website.business.display_name} — Online Booking`,
      description:
        website.tagline ||
        website.business.description ||
        `Book salon appointments online at ${website.business.display_name}.`,
    };
  } catch {
    return {
      title: "Booking Website — Svario",
      robots: { index: false, follow: false },
    };
  }
}

export default async function PublicSalonWebsitePage({
  params,
}: PublicSalonPageProps): Promise<React.JSX.Element> {
  const { slug } = await params;

  let website = null;
  try {
    website = await fetchPublicBookingWebsite(slug);
  } catch {
    notFound();
  }

  if (!website) {
    notFound();
  }

  return <PublicBookingWebsiteRenderer data={website} isPreview={false} />;
}
