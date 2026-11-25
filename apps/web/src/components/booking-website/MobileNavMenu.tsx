"use client";

import React, { useEffect, useState } from "react";

export interface MobileNavLink {
  href: string;
  label: string;
}

export interface MobileNavMenuProps {
  links: MobileNavLink[];
  breakpoint?: "sm" | "md";
  buttonClassName?: string;
  buttonStyle?: React.CSSProperties;
  panelClassName?: string;
  panelStyle?: React.CSSProperties;
  linkClassName?: string;
  linkStyle?: React.CSSProperties;
  ctaLabel?: string;
  onCtaClick?: () => void;
  ctaClassName?: string;
  ctaStyle?: React.CSSProperties;
}

/**
 * Lightweight, template-styled mobile navigation menu toggle for templates
 * whose desktop navigation links collapse on small screens.
 */
export function MobileNavMenu({
  links,
  breakpoint = "md",
  buttonClassName = "",
  buttonStyle,
  panelClassName = "",
  panelStyle,
  linkClassName = "",
  linkStyle,
  ctaLabel,
  onCtaClick,
  ctaClassName = "",
  ctaStyle,
}: MobileNavMenuProps): React.JSX.Element | null {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  if (links.length === 0) return null;

  const hiddenClass = breakpoint === "sm" ? "sm:hidden" : "md:hidden";

  return (
    <div className={`relative ${hiddenClass}`}>
      <button
        type="button"
        aria-expanded={open}
        aria-label={open ? "Close navigation menu" : "Open navigation menu"}
        data-testid="mobile-nav-toggle"
        onClick={() => setOpen((prev) => !prev)}
        className={`inline-flex min-h-[40px] min-w-[40px] items-center justify-center transition ${buttonClassName}`}
        style={buttonStyle}
      >
        <span aria-hidden="true" className="text-base leading-none">
          {open ? "✕" : "☰"}
        </span>
      </button>

      {open && (
        <nav
          aria-label="Mobile salon navigation"
          data-testid="mobile-nav-panel"
          className={`absolute right-0 top-full z-30 mt-2 w-56 max-w-[calc(100vw-2rem)] rounded-2xl border p-2 shadow-xl ${panelClassName}`}
          style={panelStyle}
        >
          <div className="flex flex-col gap-1">
            {links.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={`flex min-h-[44px] items-center rounded-xl px-3.5 py-2 text-xs font-medium transition ${linkClassName}`}
                style={linkStyle}
              >
                {item.label}
              </a>
            ))}
            {ctaLabel && onCtaClick && (
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  onCtaClick();
                }}
                className={`mt-1 flex min-h-[44px] w-full items-center justify-center px-4 py-2.5 text-xs font-semibold transition ${ctaClassName}`}
                style={ctaStyle}
              >
                {ctaLabel}
              </button>
            )}
          </div>
        </nav>
      )}
    </div>
  );
}
