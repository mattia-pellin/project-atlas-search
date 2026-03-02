import React, { useState, useEffect } from 'react';
import { Search, Loader2, Download, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import './App.css';
import { fetchDownloadLinks } from './lib/api';
import SettingsModal from './components/SettingsModal';
import ResultsTable from './components/ResultsTable';

const API_BASE = '/api';

function App() {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState([]);
  const [statuses, setStatuses] = useState({});
  const [showSettings, setShowSettings] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const [fetchingLinksFor, setFetchingLinksFor] = useState({});
  const [fetchedLinks, setFetchedLinks] = useState({});

  const [qualityFilter, setQualityFilter] = useState('All');
  const [siteFilter, setSiteFilter] = useState('All');

  const [lastSearchedQuery, setLastSearchedQuery] = useState('');

  const nonSpaceCount = query.replace(/\s/g, '').length;
  const isQueryValid = nonSpaceCount >= 4;

  const handleSearch = (e) => {
    e.preventDefault();
    if (!isQueryValid || isSearching) return;

    setLastSearchedQuery(query);
    setIsSearching(true);
    setResults([]);
    setStatuses({});
    setFetchingLinksFor({});
    setFetchedLinks({});
    setQualityFilter('All');
    setSiteFilter('All');
    setHasSearched(false);

    const eventSource = new EventSource(`${API_BASE}/search/stream?q=${encodeURIComponent(query)}`);

    eventSource.addEventListener('status', (event) => {
      const data = JSON.parse(event.data);
      setStatuses(prev => ({
        ...prev,
        [data.site]: {
          status: data.status,
          error: data.error_message || null,
          count: data.count !== undefined ? data.count : prev[data.site]?.count
        }
      }));
    });

    eventSource.addEventListener('results', (event) => {
      const data = JSON.parse(event.data);
      if (data && data.data) {
        const resultsWithId = data.data.map((r, i) => ({ ...r, id: `${data.site}-${i}-${Date.now()}` }));
        setResults(prev => [...prev, ...resultsWithId]);
        // Update status with result count
        setStatuses(prev => ({
          ...prev,
          [data.site]: { ...prev[data.site], count: data.data.length }
        }));
      }
    });

    eventSource.addEventListener('done', () => {
      eventSource.close();
      setIsSearching(false);
      setHasSearched(true);
    });

    eventSource.onerror = () => {
      eventSource.close();
      setIsSearching(false);
      setHasSearched(true);
    };
  };

  const handleFetchLinks = async (result) => {
    if (fetchedLinks[result.id]) return;

    setFetchingLinksFor(prev => ({ ...prev, [result.id]: true }));
    try {
      const payload = await fetchDownloadLinks(result.site, result.url);
      setFetchedLinks(prev => ({ ...prev, [result.id]: payload }));
      // If the detail page returned a poster, update the result
      if (payload.poster) {
        setResults(prev => prev.map(r => r.id === result.id ? { ...r, poster: payload.poster } : r));
      }
    } catch (e) {
      console.error(e);
      setFetchedLinks(prev => ({ ...prev, [result.id]: { error: 'Failed to fetch' } }));
    } finally {
      setFetchingLinksFor(prev => ({ ...prev, [result.id]: false }));
    }
  };

  const statusColors = {
    searching: '#3b82f6', // Blue
    warning: '#f59e0b',   // Orange/Amber
    completed: '#10b981', // Emerald/Green
    error: '#ef4444'      // Rose/Red
  };

  // Rendering done via ResultsTable directly

  return (
    <div className="app-container">
      <header>
        <h1 className="logo" style={{ display: 'flex', alignItems: 'center', gap: '12px', fontFamily: 'var(--logo-font)' }}>
          <img src="/logo.png" alt="Logo" style={{ width: '40px', height: '40px', display: 'block' }} />
          Project: Atlas - Search
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 'normal', alignSelf: 'flex-end', marginBottom: '4px' }}>v1.5.0</span>
        </h1>
        <button className="settings-btn" onClick={() => setShowSettings(true)}>
          <Settings size={24} />
        </button>
      </header>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}

      <div className="search-section" style={{ margin: '1.5rem 0 0.5rem 0' }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', width: '100%', maxWidth: '600px', position: 'relative' }}>
          <input
            type="text"
            className="search-input"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setHasSearched(false);
            }}
            placeholder="Search for movies, series..."
            disabled={isSearching}
          />
          <button type="submit" className="search-button" disabled={isSearching || !isQueryValid}>
            {isSearching ? <Loader2 className="animate-spin" size={24} /> : <Search size={24} />}
          </button>
        </form>

        <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap', justifyContent: 'center', marginTop: '0.8rem' }}>
          {Object.entries(statuses)
            .sort(([siteA], [siteB]) => {
              const order = ['HDItalia', 'LFI', 'Lost Planet', 'DDLWorld', 'HD4ME', '1337x'];
              const idxA = order.indexOf(siteA);
              const idxB = order.indexOf(siteB);
              if (idxA === -1 && idxB === -1) return siteA.localeCompare(siteB);
              if (idxA === -1) return 1;
              if (idxB === -1) return -1;
              return idxA - idxB;
            })
            .map(([site, info]) => {
              const status = info.status || 'searching';
              const tooltip = status === 'error'
                ? `Error: ${info.error || 'Unknown'}`
                : status === 'warning'
                  ? `Warning: ${info.error || 'Connection Refused'}`
                  : status === 'completed'
                    ? `Completed: ${info.count ?? 0} results`
                    : 'Searching...';
              return (
                <div key={site}
                  title={tooltip}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '0.5rem',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid transparent',
                    padding: '0.4rem 0.8rem', borderRadius: '20px', fontSize: '0.8rem',
                    cursor: 'help',
                    transition: 'all 0.2s'
                  }}>
                  <div style={{
                    width: '8px', height: '8px', borderRadius: '50%',
                    background: statusColors[status],
                    boxShadow: status === 'searching' ? `0 0 8px ${statusColors[status]}` : 'none',
                    animation: status === 'searching' ? 'pulse 2s infinite' : 'none'
                  }}></div>
                  <span style={{
                    textTransform: 'capitalize',
                    color: 'var(--text-secondary)',
                    fontWeight: 'normal'
                  }}>
                    {site}
                  </span>
                </div>
              );
            })}
        </div>
      </div>

      {results.length > 0 && (
        <ResultsTable
          results={results}
          fetchingLinksFor={fetchingLinksFor}
          fetchedLinks={fetchedLinks}
          onFetchLinks={handleFetchLinks}
        />
      )}

      {!isSearching && results.length === 0 && (hasSearched || (!isQueryValid && query.trim().length > 0)) && (
        <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
          {!isQueryValid ? "Inserisci almeno 4 caratteri validi (esclusi gli spazi) per avviare la ricerca." : `No results found for "${lastSearchedQuery}".`}
        </div>
      )}
    </div>
  );
}

export default App;
