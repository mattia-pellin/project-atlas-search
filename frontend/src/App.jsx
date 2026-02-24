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

  const [fetchingLinksFor, setFetchingLinksFor] = useState(null);
  const [fetchedLinks, setFetchedLinks] = useState({});

  const [qualityFilter, setQualityFilter] = useState('All');
  const [siteFilter, setSiteFilter] = useState('All');
  const [bypassCache, setBypassCache] = useState(false);

  const handleSearch = (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setResults([]);
    setStatuses({});
    setFetchingLinksFor(null);
    setFetchedLinks({});
    setQualityFilter('All');
    setSiteFilter('All');

    const cacheParam = bypassCache ? '&force_refresh=true' : '';
    const eventSource = new EventSource(`${API_BASE}/search/stream?q=${encodeURIComponent(query)}${cacheParam}`);

    eventSource.addEventListener('status', (event) => {
      const data = JSON.parse(event.data);
      setStatuses(prev => ({
        ...prev,
        [data.site]: { status: data.status, error: data.error_message || null }
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
    });

    eventSource.onerror = () => {
      eventSource.close();
      setIsSearching(false);
    };
  };

  const handleFetchLinks = async (result) => {
    if (fetchedLinks[result.id]) return;

    setFetchingLinksFor(result.id);
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
      setFetchingLinksFor(null);
    }
  };

  const statusColors = {
    searching: '#f59e0b',
    completed: '#10b981',
    error: '#ef4444'
  };

  // Rendering done via ResultsTable directly

  return (
    <div className="app-container">
      <header>
        <h1 className="logo" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Search size={32} color="var(--accent-color)" />
          Project: Atlas - Search
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 'normal', alignSelf: 'flex-end', marginBottom: '4px' }}>v1.0.0-beta</span>
        </h1>
        <button className="settings-btn" onClick={() => setShowSettings(true)}>
          <Settings size={24} />
        </button>
      </header>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}

      <div className="search-section">
        <form onSubmit={handleSearch} style={{ display: 'flex', width: '100%', maxWidth: '600px', position: 'relative' }}>
          <input
            type="text"
            className="search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search for movies, series..."
            disabled={isSearching}
          />
          <button type="submit" className="search-button" disabled={isSearching || !query.trim()}>
            {isSearching ? <Loader2 className="animate-spin" size={24} /> : <Search size={24} />}
          </button>
        </form>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '0.5rem', marginBottom: '1rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            <input
              type="checkbox"
              checked={bypassCache}
              onChange={(e) => setBypassCache(e.target.checked)}
              style={{ accentColor: 'var(--accent-color)', cursor: 'pointer' }}
              disabled={isSearching}
            />
            Bypass Cache (Force Refresh)
          </label>
        </div>

        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
          {Object.entries(statuses).map(([site, info]) => {
            const status = info.status || 'searching';
            const tooltip = status === 'error'
              ? `Error: ${info.error || 'Unknown'}`
              : status === 'completed'
                ? `Completed: ${info.count ?? '?'} results`
                : 'Searching...';
            return (
              <div key={site}
                title={tooltip}
                style={{
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  background: status === 'error' ? 'rgba(239, 68, 73, 0.1)' : 'rgba(255,255,255,0.05)',
                  border: status === 'error' ? '1px solid rgba(239, 68, 73, 0.3)' : '1px solid transparent',
                  padding: '0.5rem 1rem', borderRadius: '20px', fontSize: '0.85rem',
                  cursor: 'default'
                }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: statusColors[status] }}></div>
                <span style={{ textTransform: 'capitalize', color: status === 'error' ? '#ef4444' : 'var(--text-secondary)' }}>{site}</span>
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

      {!isSearching && results.length === 0 && query && (
        <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '2rem' }}>
          No results found for "{query}".
        </div>
      )}
    </div>
  );
}

export default App;
