import type React from "react";
import {
  APPROVED_TEMPLATE_IDS,
  type BookingWebsiteTemplateId,
} from "@/types/website";
import type { TemplateComponentProps } from "./template-utils";
import { BlushBeautyTemplate } from "./templates/BlushBeautyTemplate";
import { ClassicBeautyTemplate } from "./templates/ClassicBeautyTemplate";
import { EditorialProTemplate } from "./templates/EditorialProTemplate";
import { LuxeStudioTemplate } from "./templates/LuxeStudioTemplate";
import { MinimalEleganceTemplate } from "./templates/MinimalEleganceTemplate";
import { NoirSalonTemplate } from "./templates/NoirSalonTemplate";
import { OrganicGlowTemplate } from "./templates/OrganicGlowTemplate";
import { UrbanChicTemplate } from "./templates/UrbanChicTemplate";

export interface TemplateMetadata {
  id: BookingWebsiteTemplateId;
  code: string;
  name: string;
  tagline: string;
  description: string;
  vibe: string;
  swatches: readonly [string, string, string];
  layoutStyle:
    | "split_editorial"
    | "centered_minimal"
    | "arched_cards"
    | "grid_matrix"
    | "organic_curves"
    | "bold_pop"
    | "magazine_masthead"
    | "classic_sidebar";
  Component: React.ComponentType<TemplateComponentProps>;
}

export const TEMPLATE_REGISTRY: Readonly<Record<BookingWebsiteTemplateId, TemplateMetadata>> = {
  luxe_studio: {
    id: "luxe_studio",
    code: "01",
    name: "Luxe Studio",
    tagline: "Luxury black, gold & ivory atelier",
    description:
      "Split gold-framed hero, refined serif hierarchy, 2-column atelier service menu, and concierge booking strip.",
    vibe: "High-End Luxury",
    swatches: ["#09090B", "#D4AF37", "#F8F5EE"],
    layoutStyle: "split_editorial",
    Component: LuxeStudioTemplate,
  },
  minimal_elegance: {
    id: "minimal_elegance",
    code: "02",
    name: "Minimal Elegance",
    tagline: "White, cream & beige Nordic calm",
    description:
      "Centered airy navigation, generous whitespace, numbered vertical service index, and delicate hairline dividers.",
    vibe: "Spacious & Serene",
    swatches: ["#FAF8F4", "#E7E1D6", "#22201C"],
    layoutStyle: "centered_minimal",
    Component: MinimalEleganceTemplate,
  },
  blush_beauty: {
    id: "blush_beauty",
    code: "03",
    name: "Blush Beauty",
    tagline: "Blush pink, rose & warm ivory",
    description:
      "Arched image-led hero, interactive category filter pills, soft elevated treatment cards, and warm rose accents.",
    vibe: "Feminine & Refined",
    swatches: ["#FFF7F9", "#C96B84", "#3B2630"],
    layoutStyle: "arched_cards",
    Component: BlushBeautyTemplate,
  },
  noir_salon: {
    id: "noir_salon",
    code: "04",
    name: "Noir Salon",
    tagline: "Dark contemporary charcoal studio",
    description:
      "Asymmetric architectural grid hero, bold uppercase grotesk typography, structured service matrix, and stark CTAs.",
    vibe: "Bold & Modern",
    swatches: ["#111214", "#27272A", "#F2F2F2"],
    layoutStyle: "grid_matrix",
    Component: NoirSalonTemplate,
  },
  organic_glow: {
    id: "organic_glow",
    code: "05",
    name: "Organic Glow",
    tagline: "Earthy sage green & botanical cream",
    description:
      "Curved wellness sanctuary hero, soft rounded ritual cards, duration badges, and holistic hours presentation.",
    vibe: "Natural Wellness",
    swatches: ["#F5F3EC", "#3D5A45", "#E9EFE3"],
    layoutStyle: "organic_curves",
    Component: OrganicGlowTemplate,
  },
  urban_chic: {
    id: "urban_chic",
    code: "06",
    name: "Urban Chic",
    tagline: "Vibrant, energetic contemporary pop",
    description:
      "Oversized kinetic display headline, offset framed hero card, energetic category badges, and snappy 3-column grid.",
    vibe: "Youthful & Dynamic",
    swatches: ["#FAFAFF", "#6D28D9", "#FEF08A"],
    layoutStyle: "bold_pop",
    Component: UrbanChicTemplate,
  },
  editorial_pro: {
    id: "editorial_pro",
    code: "07",
    name: "Editorial Pro",
    tagline: "Magazine masthead & lookbook spread",
    description:
      "Editorial masthead header, asymmetric 2/3 + 1/3 hero spread, curated lookbook service directory, and colophon footer.",
    vibe: "High-Fashion Print",
    swatches: ["#FBFBF9", "#161616", "#D8D3C8"],
    layoutStyle: "magazine_masthead",
    Component: EditorialProTemplate,
  },
  classic_beauty: {
    id: "classic_beauty",
    code: "08",
    name: "Classic Beauty",
    tagline: "Clean, timeless & trustworthy studio",
    description:
      "Top contact utility bar, balanced framed hero, structured 2-column service menu, and sticky booking & hours sidebar.",
    vibe: "Timeless Professional",
    swatches: ["#FFFFFF", "#1E293B", "#F1F5F9"],
    layoutStyle: "classic_sidebar",
    Component: ClassicBeautyTemplate,
  },
};

export const TEMPLATE_CATALOG: readonly TemplateMetadata[] = APPROVED_TEMPLATE_IDS.map(
  (id) => TEMPLATE_REGISTRY[id]
);

export function isApprovedTemplateId(value: unknown): value is BookingWebsiteTemplateId {
  return (
    typeof value === "string" &&
    Object.prototype.hasOwnProperty.call(TEMPLATE_REGISTRY, value)
  );
}

/**
 * Safely resolve an approved template entry from the explicit registry.
 * Never imports arbitrary component paths; falls back safely to `luxe_studio`.
 */
export function resolveTemplateEntry(templateId: unknown): TemplateMetadata {
  if (isApprovedTemplateId(templateId)) {
    return TEMPLATE_REGISTRY[templateId];
  }
  return TEMPLATE_REGISTRY.luxe_studio;
}
