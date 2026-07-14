import { RefreshCw, Search } from "lucide-react";
import type { Security } from "../types";

interface TopBarProps {
  query: string;
  selectedSymbol: string;
  searchResults: Security[];
  isSearching: boolean;
  onQueryChange: (value: string) => void;
  onSelectSymbol: (symbol: string) => void;
  onRefresh: () => void;
}

export function TopBar({
  query,
  selectedSymbol,
  searchResults,
  isSearching,
  onQueryChange,
  onSelectSymbol,
  onRefresh
}: TopBarProps) {
  return (
    <header className="topbar">
      <div className="search-panel">
        <Search aria-hidden="true" size={18} />
        <input
          aria-label="Search local securities"
          value={query}
          placeholder="Search symbol or local security name"
          onChange={(event) => onQueryChange(event.target.value)}
        />
        {query && (
          <div className="search-results">
            {isSearching && <div className="search-row muted">Searching local database...</div>}
            {!isSearching && searchResults.length === 0 && <div className="search-row muted">No local matches.</div>}
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
      <div className="context-strip">
        <span>Context</span>
        <strong>{selectedSymbol || "No symbol selected"}</strong>
      </div>
      <button className="icon-button" onClick={onRefresh} aria-label="Refresh current view">
        <RefreshCw aria-hidden="true" size={17} />
      </button>
    </header>
  );
}
