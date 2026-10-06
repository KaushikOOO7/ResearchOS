import { useState } from "react";
import { LoaderCircle, Search, SlidersHorizontal } from "lucide-react";

const SUGGESTIONS = [
  "Graph neural networks for drug discovery",
  "AI for crop disease detection",
  "Retrieval augmented generation for healthcare",
  "Computer vision for football analytics",
  "Federated learning for IoT security",
];

/**
 * The main research input: idea -> literature.
 * Includes suggestions, a recency filter and an open-access-only toggle.
 */
export default function SearchPanel({ onSearch, status, elapsed, initialQuery = "" }) {
  const [query, setQuery] = useState(initialQuery);
  const [showOptions, setShowOptions] = useState(false);
  const [yearFrom, setYearFrom] = useState("");
  const [openAccessOnly, setOpenAccessOnly] = useState(false);

  const loading = status === "loading";

  const submit = (value = query) => {
    if (loading) return;
    onSearch(value, {
      yearFrom: yearFrom ? Number(yearFrom) : null,
      openAccessOnly,
    });
  };

  return (
    <div className="search-panel">
      <form
        className="search-box"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        role="search"
      >
        <Search size={18} className="search-box__icon" aria-hidden="true" />
        <input
          type="text"
          className="search-box__input"
          placeholder="What do you want to research?"
          aria-label="Research idea or question"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          disabled={loading}
          autoComplete="off"
          spellCheck="false"
        />
        <button
          type="button"
          className="icon-button"
          aria-label="Search options"
          aria-expanded={showOptions}
          onClick={() => setShowOptions((value) => !value)}
        >
          <SlidersHorizontal size={16} />
        </button>
        <button type="submit" className="button button--primary" disabled={loading}>
          {loading ? (
            <>
              <LoaderCircle size={16} className="spin" aria-hidden="true" />
              Researching
            </>
          ) : (
            "Research"
          )}
        </button>
      </form>

      {showOptions && (
        <div className="search-options">
          <label className="field">
            <span className="field__label">Published from</span>
            <select
              className="field__control"
              value={yearFrom}
              onChange={(event) => setYearFrom(event.target.value)}
            >
              <option value="">Any year</option>
              <option value="2026">2026</option>
              <option value="2024">2024</option>
              <option value="2020">2020</option>
              <option value="2015">2015</option>
              <option value="2010">2010</option>
            </select>
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={openAccessOnly}
              onChange={(event) => setOpenAccessOnly(event.target.checked)}
            />
            <span>Only papers with a directly accessible PDF</span>
          </label>
        </div>
      )}

      <div className="suggestions" aria-label="Example research ideas">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            className="suggestion"
            disabled={loading}
            onClick={() => {
              setQuery(suggestion);
              submit(suggestion);
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>

      {loading && (
        <p className="search-hint" aria-live="polite">
          Searching academic sources in parallel, removing duplicates and ranking
          candidates — this usually takes 5–20 seconds
          {elapsed ? ` (${elapsed}s)` : ""}.
        </p>
      )}
    </div>
  );
}
