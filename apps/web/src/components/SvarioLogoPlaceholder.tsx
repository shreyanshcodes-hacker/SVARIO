import React from "react";
import { SvarioBrandLogo, type SvarioBrandLogoProps } from "@/components/SvarioBrandLogo";

/**
 * Backward-compatible export delegating to the official `SvarioBrandLogo`.
 */
export function SvarioLogoPlaceholder(props: SvarioBrandLogoProps): React.JSX.Element {
  return <SvarioBrandLogo {...props} />;
}
