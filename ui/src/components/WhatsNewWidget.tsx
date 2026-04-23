import changelog from '../data/changelog.json'

interface ChangelogEntry {
  version: string
  date: string
  title: string
  items: string[]
}

export default function WhatsNewWidget() {
  const entries = (changelog as ChangelogEntry[]).slice(0, 3)
  return (
    <div className="whats-new-widget">
      <div className="whats-new-title">What's New</div>
      {entries.map(entry => (
        <div key={entry.version} className="whats-new-entry">
          <div className="whats-new-entry-header">
            <span className="whats-new-version">v{entry.version}</span>
            <span className="whats-new-entry-title">{entry.title}</span>
            <span className="whats-new-date">{entry.date}</span>
          </div>
          <ul className="whats-new-items">
            {entry.items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
