import { LoaderCircle, Sparkle } from "lucide-react";

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

  const statusLabel =
    health.status === "loading"
      ? "Connecting to backend…"
      : backendOnline
        ? aiReady
          ? "AI analysis online"
          : "Search online · AI key missing"
        : "Backend unreachable";

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

        <div
          className={`status ${backendOnline ? "status--ok" : "status--down"}`}
          role="status"
          title={health.data?.warnings?.join(" ") || ""}
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
