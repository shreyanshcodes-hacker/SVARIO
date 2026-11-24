"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  checkBookingWebsiteSlug,
  fetchBookingWebsiteConfig,
  fetchOnboardingBundle,
  fetchSalonServices,
  publishBookingWebsite,
  saveBookingWebsiteDraft,
  unpublishBookingWebsite,
  updateAssistantSettingsApi,
  updateBusinessLanguagesApi,
  updateBusinessProfileApi,
  uploadBookingWebsiteAsset,
} from "@/lib/api";
import type {
  AssistantPersonalityType,
  AssistantResponseStyleType,
  LanguageCodeType,
  OnboardingBundleData,
} from "@/types/platform";
import type { SalonService } from "@/types/salon";
import type {
  BookingWebsiteButtonStyleType,
  BookingWebsiteConfig,
  BookingWebsiteFontFamilyType,
  BookingWebsiteTemplateId,
  BookingWebsiteThemeType,
  PublicBookingWebsiteData,
  SlugAvailabilityResult,
} from "@/types/website";
import { TemplateGallery } from "@/components/booking-website/TemplateGallery";
import { TemplatePreview } from "@/components/booking-website/TemplatePreview";
import { resolveTemplateEntry } from "@/components/booking-website/template-registry";
import { BookingWebsiteLivePreview } from "./BookingWebsiteLivePreview";

type SectionId =
  | "overview"
  | "templates"
  | "profile"
  | "brand"
  | "url"
  | "receptionist"
  | "publish";

const SIDEBAR_ITEMS: readonly { id: SectionId; label: string; subtitle: string }[] = [
  { id: "overview", label: "Website Overview", subtitle: "Status & readiness" },
  { id: "templates", label: "Website Templates", subtitle: "8 distinct salon designs" },
  { id: "profile", label: "Business Profile", subtitle: "Contact, location & social" },
  { id: "brand", label: "Brand Studio", subtitle: "Colors, logo & typography" },
  { id: "url", label: "Website URL", subtitle: "Unique /s/ slug" },
  { id: "receptionist", label: "AI Receptionist", subtitle: "Voice persona & languages" },
  { id: "publish", label: "Preview & Publishing", subtitle: "Full preview & go live" },
];

const FONT_OPTIONS: readonly { id: BookingWebsiteFontFamilyType; label: string }[] = [
  { id: "inter", label: "Inter (Clean SaaS)" },
  { id: "plus_jakarta_sans", label: "Plus Jakarta Sans (Modern)" },
  { id: "dm_sans", label: "DM Sans (Geometric)" },
  { id: "playfair_display", label: "Playfair Display (Editorial Serif)" },
  { id: "poppins", label: "Poppins (Friendly)" },
];

const BUTTON_STYLE_OPTIONS: readonly { id: BookingWebsiteButtonStyleType; label: string }[] = [
  { id: "rounded", label: "Rounded" },
  { id: "pill", label: "Pill" },
  { id: "square", label: "Square" },
];

const ALLOWED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const MAX_IMAGE_BYTES = 2 * 1024 * 1024;

export interface BookingWebsiteWorkspaceProps {
  accessToken: string;
  organizationId: string;
  organizationName: string;
  isOwnerOrAdmin: boolean;
}

export function BookingWebsiteWorkspace({
  accessToken,
  organizationId,
  organizationName,
  isOwnerOrAdmin,
}: BookingWebsiteWorkspaceProps): React.JSX.Element {
  const [activeSection, setActiveSection] = useState<SectionId>("overview");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);

  const [config, setConfig] = useState<BookingWebsiteConfig | null>(null);
  const [bundle, setBundle] = useState<OnboardingBundleData | null>(null);
  const [services, setServices] = useState<SalonService[]>([]);

  // Website & Brand Studio state
  const [templateId, setTemplateId] = useState<BookingWebsiteTemplateId>("luxe_studio");
  const [previewTemplateId, setPreviewTemplateId] = useState<BookingWebsiteTemplateId | null>(null);
  const [slugInput, setSlugInput] = useState<string>("");
  const [slugCheck, setSlugCheck] = useState<SlugAvailabilityResult | null>(null);
  const [checkingSlug, setCheckingSlug] = useState<boolean>(false);
  const [headline, setHeadline] = useState<string>("");
  const [tagline, setTagline] = useState<string>("");
  const [primaryColor, setPrimaryColor] = useState<string>("#7657F6");
  const [secondaryColor, setSecondaryColor] = useState<string>("#36C6D3");
  const [accentColor, setAccentColor] = useState<string>("#F59E0B");
  const [backgroundColor, setBackgroundColor] = useState<string>("#0B1020");
  const [textColor, setTextColor] = useState<string>("#F5F7FC");
  const [theme, setTheme] = useState<BookingWebsiteThemeType>("dark");
  const [fontFamily, setFontFamily] = useState<BookingWebsiteFontFamilyType>("inter");
  const [buttonStyle, setButtonStyle] = useState<BookingWebsiteButtonStyleType>("rounded");
  const [socialInstagram, setSocialInstagram] = useState<string>("");
  const [socialFacebook, setSocialFacebook] = useState<string>("");
  const [socialWhatsapp, setSocialWhatsapp] = useState<string>("");
  const [showServices, setShowServices] = useState<boolean>(true);
  const [showHours, setShowHours] = useState<boolean>(true);
  const [showAiReceptionist, setShowAiReceptionist] = useState<boolean>(true);
  const [uploadingAsset, setUploadingAsset] = useState<"logo" | "cover" | null>(null);

  // Reused Business Profile state (Stage 2 onboarding API)
  const [displayName, setDisplayName] = useState<string>(organizationName);
  const [description, setDescription] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [address, setAddress] = useState<string>("");
  const [city, setCity] = useState<string>("");
  const [timezone, setTimezone] = useState<string>("Asia/Kolkata");

  // Reused AI Receptionist state (Stage 2 onboarding API)
  const [assistantName, setAssistantName] = useState<string>("Svario Receptionist");
  const [greeting, setGreeting] = useState<string>("");
  const [personality, setPersonality] = useState<AssistantPersonalityType>("warm");
  const [responseStyle, setResponseStyle] = useState<AssistantResponseStyleType>("balanced");
  const [assistantEnabled, setAssistantEnabled] = useState<boolean>(true);
  const [primaryLang, setPrimaryLang] = useState<LanguageCodeType>("en");
  const [supportedLangs, setSupportedLangs] = useState<LanguageCodeType[]>(["en"]);

  // Unpublish confirmation modal state
  const [showUnpublishConfirm, setShowUnpublishConfirm] = useState<boolean>(false);

  const hydrateFromResponses = useCallback(
    (cfg: BookingWebsiteConfig, ob: OnboardingBundleData) => {
      setConfig(cfg);
      setBundle(ob);
      setTemplateId(resolveTemplateEntry(cfg.template_id).id);
      setSlugInput(cfg.slug);
      setHeadline(cfg.headline ?? "");
      setTagline(cfg.tagline ?? "");
      setPrimaryColor(cfg.primary_color);
      setSecondaryColor(cfg.secondary_color);
      setAccentColor(cfg.accent_color);
      setBackgroundColor(cfg.background_color);
      setTextColor(cfg.text_color);
      setTheme(cfg.theme);
      setFontFamily(cfg.font_family);
      setButtonStyle(cfg.button_style);
      setSocialInstagram(cfg.social_instagram ?? "");
      setSocialFacebook(cfg.social_facebook ?? "");
      setSocialWhatsapp(cfg.social_whatsapp ?? "");
      setShowServices(cfg.show_services);
      setShowHours(cfg.show_hours);
      setShowAiReceptionist(cfg.show_ai_receptionist);

      setDisplayName(ob.profile.display_name || organizationName);
      setDescription(ob.profile.description ?? "");
      setPhone(ob.profile.phone ?? "");
      setEmail(ob.profile.email ?? "");
      setAddress(ob.profile.address ?? "");
      setCity(ob.profile.city ?? "");
      setTimezone(ob.profile.timezone || "Asia/Kolkata");

      setAssistantName(ob.assistant.assistant_name || "Svario Receptionist");
      setGreeting(ob.assistant.greeting || "");
      setPersonality(ob.assistant.personality);
      setResponseStyle(ob.assistant.response_style);
      setAssistantEnabled(ob.assistant.enabled);
      setPrimaryLang(ob.languages.primary_language);
      setSupportedLangs(ob.languages.supported_languages || ["en"]);
    },
    [organizationName]
  );

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, ob] = await Promise.all([
        fetchBookingWebsiteConfig(accessToken, organizationId),
        fetchOnboardingBundle(accessToken, organizationId),
      ]);
      hydrateFromResponses(cfg, ob);
      try {
        const svcs = await fetchSalonServices(accessToken, organizationId, ob.business_id, true);
        setServices(svcs);
      } catch {
        setServices([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load booking website settings.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, organizationId, hydrateFromResponses]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const handleSaveWebsiteDraft = async () => {
    if (!isOwnerOrAdmin) return;
    setSaving(true);
    setError(null);
    setSaveNotice(null);
    try {
      const updated = await saveBookingWebsiteDraft(accessToken, organizationId, {
        slug: slugInput.trim() || undefined,
        template_id: templateId,
        headline: headline.trim() || null,
        tagline: tagline.trim() || null,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        accent_color: accentColor,
        background_color: backgroundColor,
        text_color: textColor,
        theme,
        font_family: fontFamily,
        button_style: buttonStyle,
        social_instagram: socialInstagram.trim() || null,
        social_facebook: socialFacebook.trim() || null,
        social_whatsapp: socialWhatsapp.trim() || null,
        show_services: showServices,
        show_hours: showHours,
        show_ai_receptionist: showAiReceptionist,
      });
      setConfig(updated);
      setSlugInput(updated.slug);
      setSaveNotice("Booking website draft saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save website draft.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveBusinessProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isOwnerOrAdmin || !bundle) return;
    setSaving(true);
    setError(null);
    setSaveNotice(null);
    try {
      const updatedProfile = await updateBusinessProfileApi(accessToken, organizationId, {
        display_name: displayName.trim(),
        description: description.trim() || null,
        phone: phone.trim() || null,
        email: email.trim() || null,
        address: address.trim() || null,
        city: city.trim() || null,
        timezone: timezone.trim() || "Asia/Kolkata",
      });
      const updatedWebsite = await saveBookingWebsiteDraft(accessToken, organizationId, {
        social_instagram: socialInstagram.trim() || null,
        social_facebook: socialFacebook.trim() || null,
        social_whatsapp: socialWhatsapp.trim() || null,
      });
      setBundle({ ...bundle, profile: updatedProfile });
      setConfig(updatedWebsite);
      setSaveNotice("Business profile and social links saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save business profile.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveReceptionist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isOwnerOrAdmin || !bundle) return;
    setSaving(true);
    setError(null);
    setSaveNotice(null);
    try {
      const nextSupported = supportedLangs.includes(primaryLang)
        ? supportedLangs
        : [primaryLang, ...supportedLangs];
      const [updatedAssistant, updatedLangs] = await Promise.all([
        updateAssistantSettingsApi(accessToken, organizationId, {
          assistant_name: assistantName.trim(),
          greeting: greeting.trim(),
          personality,
          response_style: responseStyle,
          enabled: assistantEnabled,
        }),
        updateBusinessLanguagesApi(accessToken, organizationId, {
          primary_language: primaryLang,
          supported_languages: nextSupported,
        }),
      ]);
      setBundle({ ...bundle, assistant: updatedAssistant, languages: updatedLangs });
      setSaveNotice("AI receptionist settings updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save AI receptionist settings.");
    } finally {
      setSaving(false);
    }
  };

  const handleCheckSlug = async () => {
    if (!slugInput.trim()) return;
    setCheckingSlug(true);
    setError(null);
    try {
      const res = await checkBookingWebsiteSlug(accessToken, organizationId, slugInput.trim());
      setSlugCheck(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to check slug availability.");
    } finally {
      setCheckingSlug(false);
    }
  };

  const handleAssetUpload = async (
    assetType: "logo" | "cover",
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !isOwnerOrAdmin) return;
    if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
      setError("Invalid image type. Please upload a PNG, JPEG, or WEBP file.");
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setError("Image exceeds the 2 MB maximum size limit.");
      return;
    }
    setUploadingAsset(assetType);
    setError(null);
    setSaveNotice(null);
    try {
      const res = await uploadBookingWebsiteAsset(accessToken, organizationId, assetType, file);
      setConfig((prev) =>
        prev
          ? {
              ...prev,
              logo_path: assetType === "logo" ? res.storage_path : prev.logo_path,
              logo_url: assetType === "logo" ? res.public_url : prev.logo_url,
              cover_image_path: assetType === "cover" ? res.storage_path : prev.cover_image_path,
              cover_image_url: assetType === "cover" ? res.public_url : prev.cover_image_url,
            }
          : prev
      );
      setSaveNotice(`${assetType === "logo" ? "Logo" : "Cover image"} uploaded securely.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload brand image.");
    } finally {
      setUploadingAsset(null);
    }
  };

  const handleSelectTemplate = async (nextTemplateId: BookingWebsiteTemplateId) => {
    if (!isOwnerOrAdmin) return;
    setTemplateId(nextTemplateId);
    setSaving(true);
    setError(null);
    setSaveNotice(null);
    try {
      const updated = await saveBookingWebsiteDraft(accessToken, organizationId, {
        template_id: nextTemplateId,
      });
      setConfig(updated);
      setTemplateId(resolveTemplateEntry(updated.template_id).id);
      setSaveNotice(
        `Template "${resolveTemplateEntry(nextTemplateId).name}" saved to draft. Your branding, logo, and services were preserved.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save template selection.");
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!isOwnerOrAdmin) return;
    setSaving(true);
    setError(null);
    setSaveNotice(null);
    try {
      const updated = await publishBookingWebsite(accessToken, organizationId);
      setConfig(updated);
      setSaveNotice(
        `Booking website published! Live public URL: ${updated.public_url_path ?? `/s/${updated.slug}`}`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish booking website.");
    } finally {
      setSaving(false);
    }
  };

  const handleUnpublish = async () => {
    if (!isOwnerOrAdmin) return;
    setSaving(true);
    setError(null);
    setSaveNotice(null);
    try {
      const updated = await unpublishBookingWebsite(accessToken, organizationId);
      setConfig(updated);
      setShowUnpublishConfirm(false);
      setSaveNotice("Booking website set to Draft (unpublished).");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unpublish website.");
    } finally {
      setSaving(false);
    }
  };

  const toggleLanguage = (lang: LanguageCodeType) => {
    setSupportedLangs((prev) => {
      if (prev.includes(lang)) {
        if (lang === primaryLang || prev.length <= 1) return prev;
        return prev.filter((item) => item !== lang);
      }
      return [...prev, lang];
    });
  };

  const buildPreviewData = (targetTemplateId: BookingWebsiteTemplateId): PublicBookingWebsiteData => ({
    slug: slugInput || config?.slug || "your-salon",
    template_id: targetTemplateId,
    published_at: config?.published_at ?? null,
    headline: headline || null,
    tagline: tagline || null,
    logo_url: config?.logo_url ?? null,
    cover_image_url: config?.cover_image_url ?? null,
    primary_color: primaryColor,
    secondary_color: secondaryColor,
    accent_color: accentColor,
    background_color: backgroundColor,
    text_color: textColor,
    theme,
    font_family: fontFamily,
    button_style: buttonStyle,
    social_instagram: socialInstagram || null,
    social_facebook: socialFacebook || null,
    social_whatsapp: socialWhatsapp || null,
    show_services: showServices,
    show_hours: showHours,
    show_ai_receptionist: showAiReceptionist,
    business: {
      display_name: displayName || organizationName,
      description: description || null,
      phone: phone || null,
      email: email || null,
      address: address || null,
      city: city || null,
      state: bundle?.profile.state ?? null,
      country: bundle?.profile.country ?? null,
      timezone: timezone || "Asia/Kolkata",
    },
    hours: showHours ? bundle?.hours.schedule ?? [] : [],
    services: showServices
      ? services
          .filter((s) => s.is_active)
          .map((s) => ({
            id: s.id,
            name: s.name,
            category: s.category ?? null,
            description: s.description ?? null,
            duration_minutes: s.duration_minutes,
            price: s.price,
            currency: s.currency || "INR",
          }))
      : [],
    receptionist: {
      enabled: showAiReceptionist && assistantEnabled,
      assistant_name: showAiReceptionist && assistantEnabled ? assistantName : null,
      greeting: showAiReceptionist && assistantEnabled ? greeting : null,
    },
  });

  if (loading) {
    return (
      <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/80 p-10 text-center font-mono text-xs text-[#36C6D3]">
        Loading Booking Website Studio configuration...
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
      {/* Left Settings Sidebar */}
      <aside
        aria-label="Booking Website sections"
        className="h-fit rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-3"
      >
        <div className="px-3 pb-3 pt-1">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#36C6D3]">
            White-Label Engine
          </p>
          <h2 className="mt-0.5 text-sm font-bold text-[#F5F7FC]">
            Booking Website
          </h2>
        </div>
        <nav className="space-y-1">
          {SIDEBAR_ITEMS.map((item) => {
            const active = activeSection === item.id;
            return (
              <button
                key={item.id}
                type="button"
                data-testid={`website-nav-${item.id}`}
                onClick={() => setActiveSection(item.id)}
                className={`w-full rounded-xl px-3 py-2.5 text-left transition ${
                  active
                    ? "border border-[#7657F6]/60 bg-[#7657F6]/20 text-[#F5F7FC]"
                    : "border border-transparent text-[#A7B0C4] hover:bg-white/5 hover:text-[#F5F7FC]"
                }`}
              >
                <span className="block text-xs font-semibold">{item.label}</span>
                <span className="block text-[10px] opacity-80">{item.subtitle}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Main Content Area */}
      <div className="space-y-5">
        {!isOwnerOrAdmin && (
          <div className="rounded-xl border border-amber-400/35 bg-amber-950/30 px-4 py-3 text-xs text-amber-100">
            Read-only mode: Only organization owners or admins can modify booking website settings.
          </div>
        )}

        {error && (
          <div
            role="alert"
            data-testid="website-error-banner"
            className="rounded-xl border border-rose-500/40 bg-rose-950/35 px-4 py-3 text-xs text-rose-200"
          >
            {error}
          </div>
        )}

        {saveNotice && (
          <div
            role="status"
            data-testid="website-save-notice"
            className="rounded-xl border border-emerald-400/40 bg-emerald-950/30 px-4 py-3 text-xs text-emerald-200"
          >
            {saveNotice}
          </div>
        )}

        {/* 1. WEBSITE OVERVIEW */}
        {activeSection === "overview" && config && (
          <section className="space-y-5 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-4">
              <div>
                <h2 className="text-lg font-bold text-[#F5F7FC]">Website Overview</h2>
                <p className="mt-1 text-xs text-[#A7B0C4]">
                  Multi-tenant white-label booking page configuration for {displayName}.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  data-testid="website-status-badge"
                  className="rounded-lg border border-amber-400/40 bg-amber-500/15 px-3 py-1 font-mono text-xs font-bold uppercase text-amber-200"
                >
                  {config.status}
                </span>
                <button
                  type="button"
                  data-testid="overview-full-preview-button"
                  onClick={() => setPreviewTemplateId(templateId)}
                  className="rounded-xl border border-[#36C6D3]/50 bg-[#36C6D3]/15 px-3.5 py-1.5 text-xs font-semibold text-[#36C6D3] hover:bg-[#36C6D3]/25"
                >
                  Open Live Preview
                </button>
                {config.status === "published" && config.public_url_path && (
                  <Link
                    href={config.public_url_path}
                    target="_blank"
                    data-testid="overview-public-url-link"
                    className="rounded-xl border border-emerald-400/50 bg-emerald-500/15 px-3.5 py-1.5 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/25"
                  >
                    Visit Live Site ↗
                  </Link>
                )}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-[#0B1020]/75 p-4">
                <p className="font-mono text-[10px] uppercase text-[#A7B0C4]">Business Name</p>
                <p className="mt-1 text-sm font-bold text-[#F5F7FC]">{displayName}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#0B1020]/75 p-4">
                <p className="font-mono text-[10px] uppercase text-[#A7B0C4]">Public URL Path</p>
                <p className="mt-1 font-mono text-xs text-[#36C6D3]">
                  {config.public_url_path ?? `${config.preview_url_path} (Draft)`}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#0B1020]/75 p-4">
                <p className="font-mono text-[10px] uppercase text-[#A7B0C4]">Selected Template</p>
                <p className="mt-1 text-xs font-semibold text-[#F5F7FC]">
                  {resolveTemplateEntry(templateId).name}
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-[#0B1020]/75 p-4">
              <p className="font-mono text-[10px] uppercase text-[#A7B0C4]">Brand Palette & Logo</p>
              <div className="mt-2.5 flex flex-wrap items-center gap-3">
                {[
                  { label: "Primary", color: primaryColor },
                  { label: "Secondary", color: secondaryColor },
                  { label: "Accent", color: accentColor },
                  { label: "Background", color: backgroundColor },
                ].map((swatch) => (
                  <div key={swatch.label} className="flex items-center gap-2 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs">
                    <span
                      className="h-4 w-4 rounded-full border border-white/25"
                      style={{ backgroundColor: swatch.color }}
                    />
                    <span className="text-[#A7B0C4]">{swatch.label}</span>
                    <span className="font-mono text-[11px] text-[#F5F7FC]">{swatch.color}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-[#7657F6]/30 bg-[#0B1020]/75 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold text-[#F5F7FC]">Publishing Readiness</p>
                  <p className="mt-1 text-xs text-[#A7B0C4]">
                    {config.publish_readiness.stage_notice}
                  </p>
                </div>
                <button
                  type="button"
                  data-testid="overview-publish-button"
                  disabled={!config.publish_readiness.can_publish || !isOwnerOrAdmin || saving}
                  onClick={() => void handlePublish()}
                  className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#6546e6] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {config.status === "published"
                    ? "Published"
                    : config.publish_readiness.can_publish
                    ? "Publish Website"
                    : "Complete Requirements to Publish"}
                </button>
              </div>
              {config.publish_readiness.missing_requirements.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-amber-200">
                  {config.publish_readiness.missing_requirements.map((req) => (
                    <li key={req}>{req}</li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        )}

        {/* 1B. WEBSITE TEMPLATES (8 DISTINCT DESIGNS) */}
        {activeSection === "templates" && config && (
          <TemplateGallery
            selectedTemplateId={templateId}
            salonName={displayName}
            isOwnerOrAdmin={isOwnerOrAdmin}
            onSelectTemplate={(nextId) => void handleSelectTemplate(nextId)}
            onPreviewTemplate={(nextId) => setPreviewTemplateId(nextId)}
          />
        )}

        {/* 2. BUSINESS PROFILE */}
        {activeSection === "profile" && (
          <form
            onSubmit={(e) => void handleSaveBusinessProfile(e)}
            className="space-y-4 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6"
          >
            <div>
              <h2 className="text-lg font-bold text-[#F5F7FC]">Business Profile</h2>
              <p className="mt-1 text-xs text-[#A7B0C4]">
                Reuses your existing Svario business profile (single source of truth across voice & website).
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">Business Display Name</span>
                <input
                  value={displayName}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">Timezone</span>
                <input
                  value={timezone}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">Contact Phone</span>
                <input
                  value={phone}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setPhone(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">Contact Email</span>
                <input
                  type="email"
                  value={email}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">Salon Address</span>
                <input
                  value={address}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setAddress(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">City</span>
                <input
                  value={city}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setCity(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
            </div>
            <label className="block text-xs">
              <span className="text-[#A7B0C4]">Business Description</span>
              <textarea
                rows={3}
                value={description}
                disabled={!isOwnerOrAdmin}
                onChange={(e) => setDescription(e.target.value)}
                className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">Instagram</span>
                <input
                  placeholder="https://instagram.com/..."
                  value={socialInstagram}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setSocialInstagram(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">Facebook</span>
                <input
                  placeholder="https://facebook.com/..."
                  value={socialFacebook}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setSocialFacebook(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">WhatsApp</span>
                <input
                  placeholder="+91..."
                  value={socialWhatsapp}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setSocialWhatsapp(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <Link href="/onboarding" className="text-xs text-[#36C6D3] hover:underline">
                Edit full weekly opening hours in Onboarding Settings →
              </Link>
              <button
                type="submit"
                disabled={!isOwnerOrAdmin || saving}
                className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white hover:bg-[#6546e6] disabled:opacity-45"
              >
                {saving ? "Saving..." : "Save Business Profile"}
              </button>
            </div>
          </form>
        )}

        {/* 3. BRAND STUDIO */}
        {activeSection === "brand" && (
          <div className="grid gap-6 xl:grid-cols-2">
            <section className="space-y-4 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6">
              <div>
                <h2 className="text-lg font-bold text-[#F5F7FC]">Brand Studio</h2>
                <p className="mt-1 text-xs text-[#A7B0C4]">
                  Customize safe visual tokens, typography, and brand assets with live preview.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-xs">
                  <span className="text-[#A7B0C4]">Hero Headline</span>
                  <input
                    value={headline}
                    disabled={!isOwnerOrAdmin}
                    onChange={(e) => setHeadline(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  />
                </label>
                <label className="block text-xs">
                  <span className="text-[#A7B0C4]">Tagline</span>
                  <input
                    value={tagline}
                    disabled={!isOwnerOrAdmin}
                    onChange={(e) => setTagline(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {[
                  { label: "Primary", val: primaryColor, set: setPrimaryColor },
                  { label: "Secondary", val: secondaryColor, set: setSecondaryColor },
                  { label: "Accent", val: accentColor, set: setAccentColor },
                  { label: "Background", val: backgroundColor, set: setBackgroundColor },
                  { label: "Text", val: textColor, set: setTextColor },
                ].map((c) => (
                  <label key={c.label} className="block text-xs">
                    <span className="text-[#A7B0C4]">{c.label}</span>
                    <div className="mt-1 flex items-center gap-2 rounded-xl border border-white/15 bg-[#0B1020] px-2 py-1.5">
                      <input
                        type="color"
                        aria-label={`${c.label} color`}
                        value={c.val}
                        disabled={!isOwnerOrAdmin}
                        onChange={(e) => c.set(e.target.value.toUpperCase())}
                        className="h-6 w-6 cursor-pointer rounded border-0 bg-transparent"
                      />
                      <span className="font-mono text-[11px] text-[#F5F7FC]">{c.val}</span>
                    </div>
                  </label>
                ))}
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <label className="block text-xs">
                  <span className="text-[#A7B0C4]">Theme</span>
                  <select
                    value={theme}
                    disabled={!isOwnerOrAdmin}
                    onChange={(e) => {
                      const next = e.target.value as BookingWebsiteThemeType;
                      setTheme(next);
                      if (next === "light") {
                        setBackgroundColor("#F8FAFC");
                        setTextColor("#0F172A");
                      } else {
                        setBackgroundColor("#0B1020");
                        setTextColor("#F5F7FC");
                      }
                    }}
                    className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  >
                    <option value="dark">Dark</option>
                    <option value="light">Light</option>
                  </select>
                </label>

                <label className="block text-xs">
                  <span className="text-[#A7B0C4]">Typography</span>
                  <select
                    value={fontFamily}
                    disabled={!isOwnerOrAdmin}
                    onChange={(e) => setFontFamily(e.target.value as BookingWebsiteFontFamilyType)}
                    className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  >
                    {FONT_OPTIONS.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block text-xs">
                  <span className="text-[#A7B0C4]">Button Style</span>
                  <select
                    value={buttonStyle}
                    disabled={!isOwnerOrAdmin}
                    onChange={(e) => setButtonStyle(e.target.value as BookingWebsiteButtonStyleType)}
                    className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  >
                    {BUTTON_STYLE_OPTIONS.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block rounded-xl border border-dashed border-white/20 bg-[#0B1020]/70 p-3 text-xs">
                  <span className="font-semibold text-[#F5F7FC]">Upload Logo (PNG/JPEG/WEBP, max 2 MB)</span>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    disabled={!isOwnerOrAdmin || uploadingAsset !== null}
                    onChange={(e) => void handleAssetUpload("logo", e)}
                    className="mt-2 block w-full text-[11px] text-[#A7B0C4]"
                  />
                  {uploadingAsset === "logo" && (
                    <span className="mt-1 block text-[11px] text-[#36C6D3]">Uploading logo...</span>
                  )}
                </label>

                <label className="block rounded-xl border border-dashed border-white/20 bg-[#0B1020]/70 p-3 text-xs">
                  <span className="font-semibold text-[#F5F7FC]">Upload Cover Image (max 2 MB)</span>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    disabled={!isOwnerOrAdmin || uploadingAsset !== null}
                    onChange={(e) => void handleAssetUpload("cover", e)}
                    className="mt-2 block w-full text-[11px] text-[#A7B0C4]"
                  />
                  {uploadingAsset === "cover" && (
                    <span className="mt-1 block text-[11px] text-[#36C6D3]">Uploading cover...</span>
                  )}
                </label>
              </div>

              <div className="flex flex-wrap gap-4 text-xs text-[#A7B0C4]">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showServices}
                    disabled={!isOwnerOrAdmin}
                    onChange={(e) => setShowServices(e.target.checked)}
                  />
                  Show Services
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showHours}
                    disabled={!isOwnerOrAdmin}
                    onChange={(e) => setShowHours(e.target.checked)}
                  />
                  Show Hours
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showAiReceptionist}
                    disabled={!isOwnerOrAdmin}
                    onChange={(e) => setShowAiReceptionist(e.target.checked)}
                  />
                  Show AI Receptionist
                </label>
              </div>

              <button
                type="button"
                data-testid="save-brand-draft-button"
                disabled={!isOwnerOrAdmin || saving}
                onClick={() => void handleSaveWebsiteDraft()}
                className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white hover:bg-[#6546e6] disabled:opacity-45"
              >
                {saving ? "Saving Draft..." : "Save Brand Draft"}
              </button>
            </section>

            <BookingWebsiteLivePreview
              businessName={displayName}
              description={description || null}
              phone={phone || null}
              email={email || null}
              city={city || null}
              address={address || null}
              slug={slugInput}
              headline={headline}
              tagline={tagline}
              logoUrl={config?.logo_url ?? null}
              coverImageUrl={config?.cover_image_url ?? null}
              primaryColor={primaryColor}
              secondaryColor={secondaryColor}
              accentColor={accentColor}
              backgroundColor={backgroundColor}
              textColor={textColor}
              theme={theme}
              fontFamily={fontFamily}
              buttonStyle={buttonStyle}
              showServices={showServices}
              showHours={showHours}
              showAiReceptionist={showAiReceptionist}
              services={services}
              onboardingBundle={bundle}
            />
          </div>
        )}

        {/* 4. WEBSITE URL */}
        {activeSection === "url" && (
          <section className="space-y-4 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6">
            <div>
              <h2 className="text-lg font-bold text-[#F5F7FC]">Website URL Configuration</h2>
              <p className="mt-1 text-xs text-[#A7B0C4]">
                Reserve a unique slug for your salon booking website. Reserved system routes are protected.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-xl border border-white/10 bg-[#0B1020] px-3 py-2 font-mono text-xs text-[#A7B0C4]">
                svario.ai/s/
              </span>
              <input
                aria-label="Website slug"
                data-testid="website-slug-input"
                value={slugInput}
                disabled={!isOwnerOrAdmin}
                onChange={(e) => {
                  setSlugInput(e.target.value);
                  setSlugCheck(null);
                }}
                className="min-w-[220px] flex-1 rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 font-mono text-xs text-[#F5F7FC]"
              />
              <button
                type="button"
                data-testid="check-slug-button"
                disabled={checkingSlug || !slugInput.trim()}
                onClick={() => void handleCheckSlug()}
                className="rounded-xl border border-[#36C6D3]/50 bg-[#36C6D3]/15 px-3.5 py-2 text-xs font-semibold text-[#36C6D3] hover:bg-[#36C6D3]/25 disabled:opacity-45"
              >
                {checkingSlug ? "Checking..." : "Check Availability"}
              </button>
            </div>

            {slugCheck && (
              <div
                data-testid="slug-check-result"
                className={`rounded-xl border px-4 py-2.5 text-xs ${
                  slugCheck.available
                    ? "border-emerald-400/40 bg-emerald-950/30 text-emerald-200"
                    : "border-rose-500/40 bg-rose-950/30 text-rose-200"
                }`}
              >
                {slugCheck.available
                  ? `Available! Normalized URL: /s/${slugCheck.normalized_slug}`
                  : slugCheck.reason || "Slug is not available."}
              </div>
            )}

            <button
              type="button"
              data-testid="save-slug-button"
              disabled={!isOwnerOrAdmin || saving}
              onClick={() => void handleSaveWebsiteDraft()}
              className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white hover:bg-[#6546e6] disabled:opacity-45"
            >
              {saving ? "Saving..." : "Save Slug Draft"}
            </button>
          </section>
        )}

        {/* 5. AI RECEPTIONIST */}
        {activeSection === "receptionist" && (
          <form
            onSubmit={(e) => void handleSaveReceptionist(e)}
            className="space-y-4 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-[#F5F7FC]">AI Receptionist Configuration</h2>
                <p className="mt-1 text-xs text-[#A7B0C4]">
                  Shared with your existing OpenAI Realtime voice receptionist — no duplicate voice engine.
                </p>
              </div>
              <Link
                href="/voice-test"
                className="rounded-xl border border-[#36C6D3]/50 bg-[#36C6D3]/15 px-3 py-1.5 text-xs font-semibold text-[#36C6D3]"
              >
                Open Voice Test Lab
              </Link>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">Receptionist Display Name</span>
                <input
                  value={assistantName}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => setAssistantName(e.target.value)}
                  required
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                />
              </label>
              <label className="block text-xs">
                <span className="text-[#A7B0C4]">Primary Language</span>
                <select
                  value={primaryLang}
                  disabled={!isOwnerOrAdmin}
                  onChange={(e) => {
                    const next = e.target.value as LanguageCodeType;
                    setPrimaryLang(next);
                    setSupportedLangs((prev) => (prev.includes(next) ? prev : [next, ...prev]));
                  }}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                >
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="hinglish">Hinglish</option>
                </select>
              </label>
            </div>

            <label className="block text-xs">
              <span className="text-[#A7B0C4]">Greeting Message</span>
              <textarea
                rows={2}
                value={greeting}
                disabled={!isOwnerOrAdmin}
                onChange={(e) => setGreeting(e.target.value)}
                required
                className="mt-1 w-full rounded-xl border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
              />
            </label>

            <div className="flex flex-wrap items-center gap-4 text-xs text-[#A7B0C4]">
              <span>Supported Languages:</span>
              {(["en", "hi", "hinglish"] as LanguageCodeType[]).map((code) => (
                <label key={code} className="flex items-center gap-1.5 uppercase">
                  <input
                    type="checkbox"
                    checked={supportedLangs.includes(code)}
                    disabled={!isOwnerOrAdmin || code === primaryLang}
                    onChange={() => toggleLanguage(code)}
                  />
                  {code}
                </label>
              ))}
            </div>

            <label className="flex items-center gap-2 text-xs text-[#F5F7FC]">
              <input
                type="checkbox"
                checked={assistantEnabled}
                disabled={!isOwnerOrAdmin}
                onChange={(e) => setAssistantEnabled(e.target.checked)}
              />
              Enable AI Receptionist for this salon
            </label>

            <button
              type="submit"
              disabled={!isOwnerOrAdmin || saving}
              className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white hover:bg-[#6546e6] disabled:opacity-45"
            >
              {saving ? "Saving..." : "Save Receptionist Settings"}
            </button>
          </form>
        )}

        {/* 6. PREVIEW & PUBLISHING */}
        {activeSection === "publish" && config && (
          <section className="space-y-5 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-[#F5F7FC]">Preview & Publishing Foundation</h2>
                <p className="mt-1 text-xs text-[#A7B0C4]">
                  {config.publish_readiness.stage_notice}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  data-testid="open-full-page-preview-button"
                  onClick={() => setPreviewTemplateId(templateId)}
                  className="rounded-xl border border-[#36C6D3]/50 bg-[#36C6D3]/15 px-4 py-2 text-xs font-semibold text-[#36C6D3] hover:bg-[#36C6D3]/25"
                >
                  Full-Page Preview
                </button>
                <button
                  type="button"
                  disabled={!isOwnerOrAdmin || saving}
                  onClick={() => void handleSaveWebsiteDraft()}
                  className="rounded-xl border border-white/15 bg-[#0B1020] px-4 py-2 text-xs font-semibold text-[#F5F7FC] hover:border-[#36C6D3]/50 disabled:opacity-45"
                >
                  Save Draft
                </button>
                <button
                  type="button"
                  data-testid="publish-website-button"
                  disabled={!config.publish_readiness.can_publish || !isOwnerOrAdmin || saving}
                  onClick={() => void handlePublish()}
                  className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#6546e6] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {saving ? "Working..." : config.status === "published" ? "Republish Website" : "Publish Website"}
                </button>
                <button
                  type="button"
                  data-testid="unpublish-website-button"
                  disabled={!isOwnerOrAdmin || config.status !== "published" || saving}
                  onClick={() => setShowUnpublishConfirm(true)}
                  className="rounded-xl border border-rose-500/40 bg-rose-500/15 px-4 py-2 text-xs font-semibold text-rose-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Unpublish
                </button>
              </div>
            </div>

            {showUnpublishConfirm && (
              <div className="rounded-xl border border-rose-500/40 bg-rose-950/35 p-4 text-xs text-rose-100">
                <p className="font-semibold">Confirm Unpublish</p>
                <p className="mt-1">
                  Unpublishing returns your booking website to Draft status and disables public visitor access.
                </p>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => void handleUnpublish()}
                    className="rounded-lg bg-rose-600 px-3 py-1.5 font-semibold text-white"
                  >
                    Confirm Unpublish
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowUnpublishConfirm(false)}
                    className="rounded-lg border border-white/20 px-3 py-1.5 text-white"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <BookingWebsiteLivePreview
              businessName={displayName}
              description={description || null}
              phone={phone || null}
              email={email || null}
              city={city || null}
              address={address || null}
              slug={slugInput}
              headline={headline}
              tagline={tagline}
              logoUrl={config.logo_url}
              coverImageUrl={config.cover_image_url}
              primaryColor={primaryColor}
              secondaryColor={secondaryColor}
              accentColor={accentColor}
              backgroundColor={backgroundColor}
              textColor={textColor}
              theme={theme}
              fontFamily={fontFamily}
              buttonStyle={buttonStyle}
              showServices={showServices}
              showHours={showHours}
              showAiReceptionist={showAiReceptionist}
              services={services}
              onboardingBundle={bundle}
            />
          </section>
        )}
      </div>

      {/* Full-Page Responsive Template Preview Modal */}
      {previewTemplateId && (
        <TemplatePreview
          data={buildPreviewData(previewTemplateId)}
          isOpen={previewTemplateId !== null}
          isOwnerOrAdmin={isOwnerOrAdmin}
          isCurrentlySelected={previewTemplateId === templateId}
          onClose={() => setPreviewTemplateId(null)}
          onApplyTemplate={(nextId) => void handleSelectTemplate(nextId)}
        />
      )}
    </div>
  );
}
