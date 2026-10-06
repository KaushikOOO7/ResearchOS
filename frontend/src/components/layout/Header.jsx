import { LoaderCircle, Sparkle, TriangleAlert } from "lucide-react";

import { HAS_EXPLICIT_API_URL } from "../../services/api";

const NAV_ITEMS = [
  { id: "research", label: "Research" },
  { id: "papers", label: "Papers" },
  { id: "workspace", label: "Workspace" },
  { id: "about", label: "About" },
];

/** Top navigation + live backend status. */
export default function Header({
  view,
  onNavigate,
  health,
  savedCount = 0,
  analysisCount = 0,
}) {
  const backendOnline = health.status === "ready";
  const aiReady = backendOnline && health.data?.gemini_configured;
  const networkOffline = backendOnline && health.data?.network?.internet === false;
  // A deployed build without VITE_API_BASE_URL falls back to the relative
  // "/api" path, which only works behind the dev proxy. Warn instead of
  // failing silently.
  const missingApiUrl =
    import.meta.env.PROD && !HAS_EXPLICIT_API_URL && health.status !== "ready";

  const statusLabel =
    health.status === "loading"
      ? "Connecting to backend…"
      : !backendOnline
        ? "Backend unreachable"
        : networkOffline
          ? "API online · no internet egress"
          : aiReady
            ? "AI analysis online"
            : "Search online · AI key missing";

  const statusTone = !backendOnline ? "down" : networkOffline ? "warn" : "ok";

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <button
          type="button"
          className="brand"
          onClick={() => onNavigate("research")}
          aria-label="ResearchOS home"
        >
          <span className="brand__mark" aria-hidden="true">
            <Sparkle size={16} />
          </span>
          <span className="brand__text">
            Research<span className="brand__accent">OS</span>
          </span>
        </button>

        <nav className="nav" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav__item ${view === item.id ? "is-active" : ""}`}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => onNavigate(item.id)}
            >
              {item.label}
              {item.id === "papers" && savedCount > 0 && (
                <span className="nav__count" aria-label={`${savedCount} saved papers`}>
                  {savedCount}
                </span>
              )}
              {item.id === "workspace" && analysisCount > 0 && (
                <span className="nav__count" aria-label={`${analysisCount} saved analyses`}>
                  {analysisCount}
                </span>
              )}
            </button>
          ))}
        </nav>

        {missingApiUrl && (
          <span
            className="status status--warn"
            role="status"
            title="Set VITE_API_BASE_URL to your deployed backend URL (e.g. https://researchos-api.onrender.com) and rebuild."
          >
            <TriangleAlert size={13} aria-hidden="true" />
            <span className="status__label status__label--warn">VITE_API_BASE_URL not set</span>
          </span>
        )}

        <div
          className={`status status--${statusTone}`}
          role="status"
          title={
            health.data?.warnings?.join(" ") ||
            health.data?.network?.detail ||
            "Backend reachable"
          }
        >
          {health.status === "loading" ? (
            <LoaderCircle size={13} className="spin" aria-hidden="true" />
          ) : (
            <span className="status__dot" aria-hidden="true" />
          )}
          <span className="status__label">{statusLabel}</span>
        </div>
      </div>
    </header>
  );
}
