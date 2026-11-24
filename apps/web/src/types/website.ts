export type BookingWebsiteStatusType = "draft" | "published" | "disabled";
export type BookingWebsiteThemeType = "dark" | "light";
export type BookingWebsiteFontFamilyType =
  | "inter"
  | "plus_jakarta_sans"
  | "dm_sans"
  | "playfair_display"
  | "poppins";
export type BookingWebsiteButtonStyleType = "rounded" | "pill" | "square";

export interface BookingWebsitePublishReadiness {
  is_valid: boolean;
  public_engine_ready: boolean;
  can_publish: boolean;
  missing_requirements: string[];
  stage_notice: string;
}

export interface BookingWebsiteConfig {
  id: string;
  organization_id: string;
  business_id: string;
  slug: string;
  status: BookingWebsiteStatusType;
  published_at: string | null;
  headline: string | null;
  tagline: string | null;
  logo_path: string | null;
  logo_url: string | null;
  cover_image_path: string | null;
  cover_image_url: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  background_color: string;
  text_color: string;
  theme: BookingWebsiteThemeType;
  font_family: BookingWebsiteFontFamilyType;
  button_style: BookingWebsiteButtonStyleType;
  social_instagram: string | null;
  social_facebook: string | null;
  social_whatsapp: string | null;
  show_services: boolean;
  show_hours: boolean;
  show_ai_receptionist: boolean;
  preview_url_path: string;
  public_url_path: string | null;
  publish_readiness: BookingWebsitePublishReadiness;
  created_at: string;
  updated_at: string;
}

export interface BookingWebsiteDraftUpdatePayload {
  slug?: string;
  headline?: string | null;
  tagline?: string | null;
  primary_color?: string;
  secondary_color?: string;
  accent_color?: string;
  background_color?: string;
  text_color?: string;
  theme?: BookingWebsiteThemeType;
  font_family?: BookingWebsiteFontFamilyType;
  button_style?: BookingWebsiteButtonStyleType;
  social_instagram?: string | null;
  social_facebook?: string | null;
  social_whatsapp?: string | null;
  show_services?: boolean;
  show_hours?: boolean;
  show_ai_receptionist?: boolean;
}

export interface SlugAvailabilityResult {
  requested_slug: string;
  normalized_slug: string | null;
  available: boolean;
  reason: string | null;
}

export interface BrandAssetUploadResult {
  asset_type: "logo" | "cover";
  storage_path: string;
  public_url: string;
  content_type: string;
  size_bytes: number;
}
