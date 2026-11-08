"use client";

import React, { useCallback, useEffect, useState } from "react";
import { fetchBackendHealth, getApiBaseUrl } from "@/lib/api";
import type { BackendConnectionStatus } from "@/types/platform";

export function BackendStatusPanel(): React.JSX.Element {
  const [status, setStatus] = useState<BackendConnectionStatus>(() => ({
    state: "checking",
    endpoint: `${getApiBaseUrl()}/health`,
    data: null,
    latencyMs: null,
    checkedAt: null,
    errorMessage: null,
  }));

  const runHealthCheck = useCallback(async (signal?: AbortSignal) => {
    setStatus((prev) => ({
      ...prev,
      state: "checking",
      errorMessage: null,
    }));

    try {
      const result = await fetchBackendHealth(signal);
      setStatus({
        state: "connected",
        endpoint: result.endpoint,
        data: result.payload,
        latencyMs: result.latencyMs,
        checkedAt: new Date().toLocaleTimeString(),
        errorMessage: null,
      });
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      const message =
        err instanceof Error ? err.message : "Unable to reach Svario API";
      setStatus((prev) => ({
        ...prev,
        state: "unreachable",
        data: null,
        latencyMs: null,
        checkedAt: new Date().toLocaleTimeString(),
        errorMessage: message,
      }));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void runHealthCheck(controller.signal);
    return () => {
      controller.abort();
    };
  }, [runHealthCheck]);

  const badgeStyles: Record<BackendConnectionStatus["state"], string> = {
    checking:
      "border-[#7657F6]/50 bg-[#7657F6]/15 text-[#F5F7FC]",
    connected:
      "border-[#36C6D3]/60 bg-[#36C6D3]/15 text-[#36C6D3]",
    unreachable:
      "border-amber-400/50 bg-amber-500/10 text-amber-300",
  };

  const dotStyles: Record<BackendConnectionStatus["state"], string> = {
    checking: "bg-[#7657F6] animate-pulse",
    connected: "bg-[#36C6D3]",
    unreachable: "bg-amber-400",
  };

  const labelMap: Record<BackendConnectionStatus["state"], string> = {
    checking: "Checking Backend...",
    connected: "Connected — Live Health OK",
    unreachable: "Backend Offline / Unreachable",
  };

  return (
    <section
      aria-label="Backend API Connection Status"
      className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-5 shadow-[0_12px_40px_rgba(11,16,32,0.55)] backdrop-blur-md"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="font-mono text-xs font-semibold uppercase tracking-widest text-[#A7B0C4]">
              Backend Telemetry
            </span>
            <span
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-0.5 text-xs font-medium ${badgeStyles[status.state]}`}
            >
              <span
                className={`h-2 w-2 rounded-full ${dotStyles[status.state]}`}
              />
              {labelMap[status.state]}
            </span>
          </div>
          <p className="text-sm text-[#A7B0C4]">
            Probing FastAPI health contract at{" "}
            <code className="rounded bg-[#0B1020] px-2 py-0.5 font-mono text-xs text-[#F5F7FC]">
              GET {status.endpoint}
            </code>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {status.data ? (
            <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
              <span className="rounded-lg border border-[#A7B0C4]/20 bg-[#0B1020] px-2.5 py-1.5 text-[#F5F7FC]">
                status:{" "}
                <strong className="text-[#36C6D3]">{status.data.status}</strong>
              </span>
              <span className="rounded-lg border border-[#A7B0C4]/20 bg-[#0B1020] px-2.5 py-1.5 text-[#F5F7FC]">
                service:{" "}
                <strong className="text-[#F5F7FC]">{status.data.service}</strong>
              </span>
              <span className="rounded-lg border border-[#A7B0C4]/20 bg-[#0B1020] px-2.5 py-1.5 text-[#F5F7FC]">
                stage:{" "}
                <strong className="text-[#7657F6]">{status.data.stage}</strong>
              </span>
              {status.latencyMs !== null && (
                <span className="rounded-lg border border-[#A7B0C4]/20 bg-[#0B1020] px-2.5 py-1.5 text-[#A7B0C4]">
                  {status.latencyMs} ms
                </span>
              )}
            </div>
          ) : status.state === "unreachable" ? (
            <span className="rounded-lg border border-amber-400/30 bg-[#0B1020]/90 px-3 py-1.5 font-mono text-xs text-amber-200">
              Start API on port 8000 to verify live connection ({status.errorMessage})
            </span>
          ) : null}

          <button
            type="button"
            onClick={() => void runHealthCheck()}
            disabled={status.state === "checking"}
            className="inline-flex items-center gap-1.5 rounded-xl border border-[#7657F6]/60 bg-[#7657F6]/20 px-3.5 py-2 text-xs font-semibold text-[#F5F7FC] transition hover:bg-[#7657F6]/35 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span>Re-check Health</span>
          </button>
        </div>
      </div>
    </section>
  );
}
