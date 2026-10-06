/**
 * Bullet list for analysis items.
 *
 * `tone` communicates provenance:
 *   fact    -> stated in the paper (green)
 *   inferred-> AI-inferred analysis (amber)
 *   neutral -> mixed / structural
 */
export default function BulletList({ items, tone = "neutral", emptyText = "Not stated in the provided paper." }) {
  if (!items || items.length === 0) {
    return <p className="muted">{emptyText}</p>;
  }

  return (
    <ul className={`bullet-list bullet-list--${tone}`}>
      {items.map((item, index) => (
        <li key={`${index}-${item.slice(0, 24)}`}>
          <span className="bullet-list__dot" aria-hidden="true" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
