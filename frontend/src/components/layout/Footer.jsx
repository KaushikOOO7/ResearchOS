import { Sparkle } from "lucide-react";

/** Footer with an honest statement of what is and is not implemented. */
export default function Footer({ health, onNavigate }) {
  return (
    <footer className="app-footer">
      <div className="app-footer__inner">
        <div className="app-footer__brand">
          <Sparkle size={14} aria-hidden="true" />
          <span>ResearchOS</span>
          <span className="app-footer__version">
            v{health.data?.version || "1.0.0"}
          </span>
        </div>

        <p className="app-footer__note">
          Real academic sources only — ResearchOS never fabricates papers,
          citations or analysis. Papers that lack metadata are labelled
          “Not available”, and AI output always distinguishes what the paper
          states from what the model infers.
        </p>

        <button type="button" className="link-button" onClick={() => onNavigate("about")}>
          Methodology &amp; roadmap
        </button>
      </div>
    </footer>
  );
}
