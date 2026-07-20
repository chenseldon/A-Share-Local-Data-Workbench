import { Search } from "lucide-react";
import type { Security } from "../types";

interface TopBarProps {
  query: string;
  searchResults: Security[];
  isSearching: boolean;
  onQueryChange: (value: string) => void;
  onSelectSymbol: (symbol: string) => void;
}

export function TopBar({
  query,
  searchResults,
  isSearching,
  onQueryChange,
  onSelectSymbol
}: TopBarProps) {
  return (
    <header className="topbar">
      <div className="search-panel">
        <Search aria-hidden="true" size={18} />
        <input
          aria-label="Search or resolve A-share symbol"
          value={query}
          placeholder="Search symbol, name, or type 600519"
          onChange={(event) => onQueryChange(event.target.value)}
        />
        {query && (
          <div className="search-results">
            {isSearching && <div className="search-row muted">Searching local free-stockdb directory...</div>}
            {!isSearching && searchResults.length === 0 && (
              <div className="search-row muted">No local free-stockdb match.</div>
            )}
            {searchResults.map((security) => (
              <button key={security.symbol} className="search-row" onClick={() => onSelectSymbol(security.symbol)}>
                <span>{security.symbol}</span>
                <strong>{security.name}</strong>
                <small>{security.exchange}</small>
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  );
}
