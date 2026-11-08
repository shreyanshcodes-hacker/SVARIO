import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let browserClient: SupabaseClient | null = null;

export function getSupabaseConfig(): {
  url: string;
  anonKey: string;
  isConfigured: boolean;
} {
  const url = (process.env.NEXT_PUBLIC_SUPABASE_URL ?? "").trim();
  const anonKey = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "").trim();

  const isConfigured =
    url.length > 0 &&
    anonKey.length > 0 &&
    !url.includes("your-project-ref") &&
    !anonKey.includes("placeholder");

  return {
    url: url || "https://placeholder-project.supabase.co",
    anonKey: anonKey || "placeholder-anon-key",
    isConfigured,
  };
}

export function isSupabaseConfigured(): boolean {
  return getSupabaseConfig().isConfigured;
}

export function getSupabaseBrowserClient(): SupabaseClient {
  if (browserClient) {
    return browserClient;
  }

  const { url, anonKey } = getSupabaseConfig();
  browserClient = createClient(url, anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });

  return browserClient;
}

export function getAuthRedirectUrl(path: string): string {
  const configuredSiteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "").trim();
  const cleanPath = path.startsWith("/") ? path : `/${path}`;

  if (configuredSiteUrl.length > 0) {
    return `${configuredSiteUrl.replace(/\/+$/, "")}${cleanPath}`;
  }

  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}${cleanPath}`;
  }

  return `http://localhost:3000${cleanPath}`;
}
