import type {
  BookingWebsiteTemplateId,
  PublicBookingWebsiteData,
} from "@/types/website";
import { resolveTemplateEntry } from "../template-registry";
import { getButtonRadiusClass, getFontFamilyStack } from "../template-utils";

export interface ReceptionistTemplateTheme {
  templateId: BookingWebsiteTemplateId;
  templateName: string;
  isDark: boolean;
  fontFamily: string;
  buttonRadiusClass: string;
  surfaceBg: string;
  surfaceElevatedBg: string;
  borderColor: string;
  textPrimary: string;
  textMuted: string;
  accentBg: string;
  accentText: string;
  badgeBg: string;
  badgeText: string;
  launcherShadowClass: string;
  panelShadowClass: string;
  headingClass: string;
}

/**
 * Non-invasive presentation adapter that derives AI Receptionist UI tokens
 * directly from the resolved published website's `template_id` and brand settings.
 * Zero edits to the 8 locked template components; zero global CSS side effects.
 */
export function resolveReceptionistTemplateTheme(
  data: PublicBookingWebsiteData
): ReceptionistTemplateTheme {
  const entry = resolveTemplateEntry(data.template_id);
  const fontFamily = getFontFamilyStack(data.font_family);
  const buttonRadiusClass = getButtonRadiusClass(data.button_style);

  switch (entry.id) {
    case "luxe_studio":
      return {
        templateId: entry.id,
        templateName: entry.name,
        isDark: true,
        fontFamily,
        buttonRadiusClass,
        surfaceBg: "#09090B",
        surfaceElevatedBg: "#141310",
        borderColor: "rgba(212, 175, 55, 0.45)",
        textPrimary: "#F8F5EE",
        textMuted: "#C9C2B2",
        accentBg: data.accent_color || "#D4AF37",
        accentText: "#09090B",
        badgeBg: "rgba(212, 175, 55, 0.14)",
        badgeText: "#D4AF37",
        launcherShadowClass: "shadow-xl shadow-black/60",
        panelShadowClass: "shadow-2xl shadow-black/75",
        headingClass: "font-serif tracking-[0.08em]",
      };

    case "minimal_elegance":
      return {
        templateId: entry.id,
        templateName: entry.name,
        isDark: false,
        fontFamily,
        buttonRadiusClass,
        surfaceBg: "#FAF8F4",
        surfaceElevatedBg: "#FFFFFF",
        borderColor: "#E7E1D6",
        textPrimary: "#1E1C19",
        textMuted: "#6E685D",
        accentBg: "#22201C",
        accentText: "#FAF8F4",
        badgeBg: "#F1ECE3",
        badgeText: "#59544A",
        launcherShadowClass: "shadow-lg shadow-stone-900/10",
        panelShadowClass: "shadow-2xl shadow-stone-900/15",
        headingClass: "font-light tracking-tight",
      };

    case "blush_beauty":
      return {
        templateId: entry.id,
        templateName: entry.name,
        isDark: false,
        fontFamily,
        buttonRadiusClass,
        surfaceBg: "#FFF7F9",
        surfaceElevatedBg: "#FFFFFF",
        borderColor: "#F3D8E0",
        textPrimary: "#3B2630",
        textMuted: "#7D5665",
        accentBg: "#C96B84",
        accentText: "#FFFFFF",
        badgeBg: "#FBE5EC",
        badgeText: "#9D3F59",
        launcherShadowClass: "shadow-lg shadow-rose-900/15",
        panelShadowClass: "shadow-2xl shadow-rose-900/20",
        headingClass: "font-serif font-semibold",
      };

    case "noir_salon":
      return {
        templateId: entry.id,
        templateName: entry.name,
        isDark: true,
        fontFamily,
        buttonRadiusClass,
        surfaceBg: "#111214",
        surfaceElevatedBg: "#18191C",
        borderColor: "rgba(255, 255, 255, 0.2)",
        textPrimary: "#F2F2F2",
        textMuted: "#A1A1AA",
        accentBg: "#FFFFFF",
        accentText: "#111214",
        badgeBg: "rgba(255, 255, 255, 0.08)",
        badgeText: "#E4E4E7",
        launcherShadowClass: "shadow-xl shadow-black/70",
        panelShadowClass: "shadow-2xl shadow-black/80",
        headingClass: "font-black uppercase tracking-wider",
      };

    case "organic_glow":
      return {
        templateId: entry.id,
        templateName: entry.name,
        isDark: false,
        fontFamily,
        buttonRadiusClass,
        surfaceBg: "#FCFBF7",
        surfaceElevatedBg: "#E9EFE3",
        borderColor: "#DCE2D4",
        textPrimary: "#243228",
        textMuted: "#4C5F51",
        accentBg: "#3D5A45",
        accentText: "#FCFBF7",
        badgeBg: "#E9EFE3",
        badgeText: "#2E4635",
        launcherShadowClass: "shadow-lg shadow-emerald-950/15",
        panelShadowClass: "shadow-2xl shadow-emerald-950/20",
        headingClass: "font-serif",
      };

    case "urban_chic":
      return {
        templateId: entry.id,
        templateName: entry.name,
        isDark: false,
        fontFamily,
        buttonRadiusClass,
        surfaceBg: "#FAFAFF",
        surfaceElevatedBg: "#FFFFFF",
        borderColor: "#12131F",
        textPrimary: "#12131F",
        textMuted: "#474B66",
        accentBg: data.primary_color || "#6D28D9",
        accentText: "#FFFFFF",
        badgeBg: "#FEF08A",
        badgeText: "#12131F",
        launcherShadowClass: "border-2 shadow-[4px_4px_0px_#12131F]",
        panelShadowClass: "border-2 shadow-[8px_8px_0px_#12131F]",
        headingClass: "font-black tracking-tight",
      };

    case "editorial_pro":
      return {
        templateId: entry.id,
        templateName: entry.name,
        isDark: false,
        fontFamily,
        buttonRadiusClass,
        surfaceBg: "#FBFBF9",
        surfaceElevatedBg: "#F2F0EA",
        borderColor: "#161616",
        textPrimary: "#161616",
        textMuted: "#5E5E5E",
        accentBg: "#161616",
        accentText: "#FBFBF9",
        badgeBg: "#EAE8E1",
        badgeText: "#161616",
        launcherShadowClass: "shadow-lg shadow-black/15",
        panelShadowClass: "shadow-2xl shadow-black/25",
        headingClass: "font-serif tracking-[0.06em] uppercase",
      };

    case "classic_beauty":
    default:
      return {
        templateId: entry.id,
        templateName: entry.name,
        isDark: false,
        fontFamily,
        buttonRadiusClass,
        surfaceBg: "#FFFFFF",
        surfaceElevatedBg: "#F8FAFC",
        borderColor: "#CBD5E1",
        textPrimary: "#0F172A",
        textMuted: "#475569",
        accentBg: data.primary_color || "#1E293B",
        accentText: "#FFFFFF",
        badgeBg: "#F1F5F9",
        badgeText: "#1E293B",
        launcherShadowClass: "shadow-lg shadow-slate-900/15",
        panelShadowClass: "shadow-2xl shadow-slate-900/20",
        headingClass: "font-serif font-bold",
      };
  }
}
