import React, { useState, useEffect } from 'react';
import { Search, Loader2, Download, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import './App.css';
import { fetchDownloadLinks } from './lib/api';
import SettingsModal from './components/SettingsModal';

const API_BASE = 'http://localhost:8080/api';

function App() {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState([]);
  const [statuses, setStatuses] = useState({});
  const [showSettings, setShowSettings] = useState(false);

  // For expandable rows
  const [expandedId, setExpandedId] = useState(null);
  const [fetchingLinksFor, setFetchingLinksFor] = useState(null);
  const [fetchedLinks, setFetchedLinks] = useState({});

  const [qualityFilter, setQualityFilter] = useState('All');
  const [siteFilter, setSiteFilter] = useState('All');

  const handleSearch = (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setResults([]);
    setStatuses({});
    setExpandedId(null);
    setFetchingLinksFor(null);
    setFetchedLinks({});
    setQualityFilter('All');
    setSiteFilter('All');

    const eventSource = new EventSource(`${API_BASE}/search/stream?q=${encodeURIComponent(query)}`);

    eventSource.addEventListener('status', (event) => {
      const data = JSON.parse(event.data);
      setStatuses(prev => ({ ...prev, [data.site]: data.status }));
    });

    eventSource.addEventListener('results', (event) => {
      const data = JSON.parse(event.data);
      if (data && data.data) {
        const resultsWithId = data.data.map((r, i) => ({ ...r, id: `${data.site}-${i}-${Date.now()}` }));
        setResults(prev => [...prev, ...resultsWithId]);
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
    if (expandedId === result.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(result.id);

    if (fetchedLinks[result.id]) return;

    setFetchingLinksFor(result.id);
    try {
      const payload = await fetchDownloadLinks(result.site, result.url);
      setFetchedLinks(prev => ({ ...prev, [result.id]: payload }));
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

  const qualityRank = {
    '2160p': 8,
    '2160i': 7,
    '1080p': 6,
    '1080i': 5,
    '720p': 4,
    '720i': 3,
    '576p': 2,
    '576i': 1,
    '480p': 0,
    '480i': -1,
    'sd': -2,
    'n/a': -3
  };

  const sortedAndFilteredResults = results
    .filter(r => {
      const qMatches = qualityFilter === 'All' || (r.quality || 'N/A').toLowerCase() === qualityFilter.toLowerCase();
      const sMatches = siteFilter === 'All' || r.site === siteFilter;
      return qMatches && sMatches;
    })
    .sort((a, b) => {
      const qA = qualityRank[(a.quality || 'N/A').toLowerCase()] ?? -3;
      const qB = qualityRank[(b.quality || 'N/A').toLowerCase()] ?? -3;
      if (qA !== qB) return qB - qA;

      const parseDate = (d) => {
        if (!d || d === 'Unknown') return 0;
        const parts = d.split('/');
        if (parts.length === 3) return new Date(`${parts[2]}-${parts[1]}-${parts[0]}`).getTime();
        return 0;
      };
      return parseDate(b.date) - parseDate(a.date);
    });

  const uniqueQualities = ['All', ...new Set(results.map(r => r.quality || 'N/A'))].filter(Boolean);
  const uniqueSites = ['All', ...new Set(results.map(r => r.site))].filter(Boolean);

  return (
    <div className="app-container">
      <header>
        <h1 className="logo"><Search size={32} color="var(--accent-color)" /> Atlas Search</h1>
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

        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
          {Object.entries(statuses).map(([site, status]) => (
            <div key={site} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.05)', padding: '0.5rem 1rem', borderRadius: '20px', fontSize: '0.85rem' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: statusColors[status] }}></div>
              <span style={{ textTransform: 'capitalize', color: 'var(--text-secondary)' }}>{site}</span>
            </div>
          ))}
        </div>
      </div>

      {results.length > 0 && (
        <>
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', padding: '0 0.5rem' }} className="animate-fade-in">
            <select value={qualityFilter} onChange={e => setQualityFilter(e.target.value)} style={{ padding: '0.5rem 1rem', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', color: 'white', border: '1px solid var(--glass-border)', cursor: 'pointer' }}>
              {uniqueQualities.map(q => <option style={{ background: '#1a1a1a' }} key={q} value={q}>{q === 'All' ? 'All Qualities' : q}</option>)}
            </select>
            <select value={siteFilter} onChange={e => setSiteFilter(e.target.value)} style={{ padding: '0.5rem 1rem', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', color: 'white', border: '1px solid var(--glass-border)', cursor: 'pointer' }}>
              {uniqueSites.map(s => <option style={{ background: '#1a1a1a' }} key={s} value={s}>{s === 'All' ? 'All Sites' : s}</option>)}
            </select>
          </div>
          <div className="results-table-container animate-fade-in">
            <table className="results-table">
              <thead>
                <tr>
                  <th style={{ width: '60px', textAlign: 'center' }}>Cover</th>
                  <th>Title</th>
                  <th style={{ width: '100px' }}>Date</th>
                  <th style={{ width: '100px' }}>Quality</th>
                  <th style={{ width: '120px' }}>Site</th>
                  <th style={{ width: '120px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <React.Fragment key={r.id}>
                    <tr className={expandedId === r.id ? 'expanded' : ''}>
                      <td style={{ textAlign: 'center' }}>
                        {r.poster ? (
                          <img src={r.poster} alt="poster" style={{ width: '40px', height: '60px', objectFit: 'cover', borderRadius: '4px' }} />
                        ) : (
                          <div style={{ width: '40px', height: '60px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', color: '#666' }}>N/A</div>
                        )}
                      </td>
                      <td style={{ fontWeight: 500 }}>
                        <a href={r.url} target="_blank" rel="noreferrer" style={{ color: 'var(--text-primary)', textDecoration: 'none' }}>
                          {r.title}
                        </a>
                      </td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{r.date || 'Unknown'}</td>
                      <td>
                        <span className={`quality-badge ${(r.quality === '1080P' || r.quality === '720P') ? 'hd' : (r.quality === '2160P' || r.quality === '4K') ? 'uhd' : ''}`}>
                          {r.quality || 'SD'}
                        </span>
                      </td>
                      <td>
                        <span style={{ background: 'rgba(255,255,255,0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem', textTransform: 'capitalize' }}>
                          {r.site}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          onClick={() => handleFetchLinks(r)}
                          style={{
                            background: 'var(--accent-color)', color: 'white', border: 'none',
                            padding: '0.5rem 1rem', borderRadius: '6px', cursor: 'pointer',
                            display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
                            fontWeight: 600, fontSize: '0.85rem'
                          }}
                        >
                          {fetchingLinksFor === r.id ? <Loader2 className="animate-spin" size={16} /> : (expandedId === r.id ? <ChevronUp size={16} /> : <Download size={16} />)}
                          {expandedId === r.id ? 'Hide' : 'Links'}
                        </button>
                      </td>
                    </tr>

                    {/* Expanded Row for Links */}
                    {expandedId === r.id && (
                      <tr style={{ background: 'rgba(0,0,0,0.2)' }}>
                        <td colSpan={6} style={{ padding: '1.5rem', borderBottom: '1px solid var(--glass-border)' }}>
                          {fetchingLinksFor === r.id && <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}><Loader2 className="animate-spin" size={16} /> Extracting secure links...</div>}

                          {!fetchingLinksFor && fetchedLinks[r.id] && (
                            <div className="animate-fade-in">
                              {fetchedLinks[r.id].error ? (
                                <div style={{ color: '#ef4444' }}>Error: {fetchedLinks[r.id].error}</div>
                              ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                  {fetchedLinks[r.id].password && (
                                    <div style={{ background: 'rgba(255,255,255,0.05)', padding: '0.75rem', borderRadius: '8px', display: 'inline-block', alignSelf: 'flex-start' }}>
                                      <span style={{ color: 'var(--text-secondary)', marginRight: '0.5rem' }}>Archive Password:</span>
                                      <code style={{ background: 'rgba(0,0,0,0.3)', padding: '0.2rem 0.5rem', borderRadius: '4px', color: 'var(--accent-color)', fontWeight: 'bold' }}>
                                        {fetchedLinks[r.id].password}
                                      </code>
                                    </div>
                                  )}

                                  {fetchedLinks[r.id].links?.length > 0 ? (
                                    <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                      {fetchedLinks[r.id].links.map((link, idx) => (
                                        <li key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                          <div style={{ width: '6px', height: '6px', background: 'var(--accent-color)', borderRadius: '50%' }}></div>
                                          <a href={link} target="_blank" rel="noreferrer" style={{ color: '#58a6ff', textDecoration: 'none', wordBreak: 'break-all' }}>
                                            {link}
                                          </a>
                                        </li>
                                      ))}
                                    </ul>
                                  ) : (
                                    <div style={{ color: 'var(--text-secondary)' }}>No external links found on this page.</div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
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
