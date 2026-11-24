import type {
  BookingWebsiteButtonStyleType,
  BookingWebsiteFontFamilyType,
  PublicBookingWebsiteData,
  PublicBusinessHourItem,
  PublicSalonServiceItem,
} from "@/types/website";

export interface TemplateComponentProps {
  data: PublicBookingWebsiteData;
  onBookClick?: (service?: PublicSalonServiceItem) => void;
  isPreview?: boolean;
}

const WEEKDAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const;

export function formatWeekdayName(weekday: number): string {
  return WEEKDAY_NAMES[weekday] ?? `Day ${weekday}`;
}

export function formatShortWeekday(weekday: number): string {
  return formatWeekdayName(weekday).slice(0, 3);
}

export function formatHourRange(item: PublicBusinessHourItem): string {
  if (item.is_closed || !item.opens_at || !item.closes_at) {
    return "Closed";
  }
  return `${item.opens_at} – ${item.closes_at}`;
}

export function formatServicePrice(price: number, currency: string): string {
  const code = (currency || "INR").toUpperCase();
  if (code === "INR") {
    return `₹${Number.isInteger(price) ? price.toLocaleString("en-IN") : price.toFixed(2)}`;
  }
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: code,
      maximumFractionDigits: Number.isInteger(price) ? 0 : 2,
    }).format(price);
  } catch {
    return `${code} ${price.toFixed(0)}`;
  }
}

export function getButtonRadiusClass(style: BookingWebsiteButtonStyleType): string {
  switch (style) {
    case "pill":
      return "rounded-full";
    case "square":
      return "rounded-none";
    case "rounded":
    default:
      return "rounded-xl";
  }
}

export function getFontFamilyStack(font: BookingWebsiteFontFamilyType): string {
  switch (font) {
    case "playfair_display":
      return "'Playfair Display', Georgia, 'Times New Roman', serif";
    case "plus_jakarta_sans":
      return "'Plus Jakarta Sans', ui-sans-serif, system-ui, sans-serif";
    case "dm_sans":
      return "'DM Sans', ui-sans-serif, system-ui, sans-serif";
    case "poppins":
      return "'Poppins', ui-sans-serif, system-ui, sans-serif";
    case "inter":
    default:
      return "Inter, ui-sans-serif, system-ui, sans-serif";
  }
}

export function groupServicesByCategory(
  services: PublicSalonServiceItem[]
): { category: string; items: PublicSalonServiceItem[] }[] {
  const map = new Map<string, PublicSalonServiceItem[]>();
  for (const svc of services) {
    const key = (svc.category || "Signature Services").trim() || "Signature Services";
    const list = map.get(key) ?? [];
    list.push(svc);
    map.set(key, list);
  }
  return Array.from(map.entries()).map(([category, items]) => ({ category, items }));
}

export function formatFullAddress(data: PublicBookingWebsiteData): string | null {
  const parts = [
    data.business.address,
    data.business.city,
    data.business.state,
    data.business.country,
  ]
    .map((p) => (p || "").trim())
    .filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : null;
}

export function safeExternalHref(raw: string | null, platform: "instagram" | "facebook" | "whatsapp"): string | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const lower = trimmed.toLowerCase();
  if (lower.startsWith("javascript:") || lower.startsWith("data:") || lower.startsWith("vbscript:")) {
    return null;
  }
  if (lower.startsWith("http://") || lower.startsWith("https://")) {
    return trimmed;
  }
  if (platform === "instagram") {
    return `https://instagram.com/${trimmed.replace(/^@/, "")}`;
  }
  if (platform === "facebook") {
    return `https://facebook.com/${trimmed.replace(/^@/, "")}`;
  }
  const digits = trimmed.replace(/[^\d]/g, "");
  return digits ? `https://wa.me/${digits}` : null;
}
