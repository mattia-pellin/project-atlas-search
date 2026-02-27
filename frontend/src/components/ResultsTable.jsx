import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { Download, ChevronDown, ChevronUp, Loader2, Filter, ArrowUpDown, GripVertical, ImageOff, Link, Magnet, KeyRound, Check, Shield, Link2 } from 'lucide-react';

const HOSTER_ICONS = {
    magnet: { Icon: Magnet, color: '#ef4444' },
    torrent: { Icon: Download, color: '#22c55e' }
};

const stringToColor = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = hash % 360;
    return `hsl(${hue < 0 ? hue + 360 : hue}, 75%, 60%)`;
};

const getHosterDomain = (link) => {
    if (link.startsWith('magnet:')) return 'magnet';
    try {
        const url = new URL(link);
        return url.hostname.replace(/^www\./, '');
    } catch (e) {
        if (link.includes('torrent')) return 'torrent';
        return 'unknown';
    }
};

const groupLinks = (links) => {
    const groups = {};
    (links || []).forEach(link => {
        const h = getHosterDomain(link);
        if (!groups[h]) groups[h] = [];
        groups[h].push(link);
    });
    return groups;
};

export default function ResultsTable({ results, fetchingLinksFor, fetchedLinks, onFetchLinks }) {
    const [expandedId, setExpandedId] = useState(null);
    const [activeHoster, setActiveHoster] = useState({});
    const [toastMsg, setToastMsg] = useState(null);
    const [imageErrors, setImageErrors] = useState({});
    const toastTimer = useRef(null);

    const showToast = useCallback((msg) => {
        if (toastTimer.current) clearTimeout(toastTimer.current);
        setToastMsg(msg);
        toastTimer.current = setTimeout(() => setToastMsg(null), 2000);
    }, []);
    // Column Definitions
    const initialColumns = [
        { id: 'cover', label: 'Cover', width: '60px', sortable: false, filterable: false },
        { id: 'title', label: 'Title', width: 'auto', sortable: true, filterable: false },
        { id: 'date', label: 'Date', width: '120px', sortable: true, filterable: false },
        { id: 'quality', label: 'Quality', width: '100px', sortable: true, filterable: true },
        { id: 'metadata', label: 'Metadata', width: '250px', sortable: false, filterable: true },
        { id: 'site', label: 'Site', width: '120px', sortable: true, filterable: true },
        { id: 'actions', label: 'Actions', width: '150px', sortable: false, filterable: false }
    ];

    const [columns, setColumns] = useState(initialColumns);
    const [sortConfig, setSortConfig] = useState({ key: 'auto', direction: 'desc' });
    const [filters, setFilters] = useState({ quality: new Set(), site: new Set(), metadata: new Set() });
    const [activeFilterMenu, setActiveFilterMenu] = useState(null);

    const filterMenuRef = useRef(null);

    // Close click outside
    useEffect(() => {
        function handleClickOutside(event) {
            if (filterMenuRef.current && !filterMenuRef.current.contains(event.target)) {
                setActiveFilterMenu(null);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Derived Unique Values for Filters
    const qualityRank = {
        '2160p': 8, '4k': 8, '2160i': 7, '1080p': 6, '1080i': 5,
        '720p': 4, '720i': 3, '576p': 2, '576i': 1, '480p': 0, '480i': -1, 'sd': -2, 'n/a': -3
    };

    const uniqueValues = useMemo(() => {
        const qualities = [...new Set(results.map(r => r.quality || 'N/A'))].filter(Boolean);
        qualities.sort((a, b) => {
            const ra = qualityRank[a.toLowerCase()] ?? -3;
            const rb = qualityRank[b.toLowerCase()] ?? -3;
            return rb - ra; // highest first
        });

        // Metadata unique values (collect all non-null values from codec, audio, source, hdr)
        const metaValues = new Set();
        results.forEach(r => {
            if (r.metadata) {
                Object.values(r.metadata).forEach(v => {
                    if (v) metaValues.add(v);
                });
            }
        });

        return {
            quality: qualities,
            site: [...new Set(results.map(r => r.site))].filter(Boolean).sort(),
            metadata: [...metaValues].sort()
        };
    }, [results]);

    // Apply Sorting and Filtering
    const processedResults = useMemo(() => {
        let filtered = results.filter(row => {
            if (filters.quality.size > 0 && !filters.quality.has(row.quality || 'N/A')) return false;
            if (filters.site.size > 0 && !filters.site.has(row.site)) return false;
            if (filters.metadata.size > 0) {
                const rowMeta = row.metadata ? Object.values(row.metadata).filter(Boolean) : [];
                if (!rowMeta.some(v => filters.metadata.has(v))) return false;
            }
            return true;
        });

        // qualityRank is defined at component level above

        if (sortConfig.key) {
            filtered.sort((a, b) => {
                let valA = a[sortConfig.key];
                let valB = b[sortConfig.key];

                if (sortConfig.key === 'auto') {
                    // special auto-sort: Quality (desc) -> Date (desc)
                    let qA = qualityRank[(a.quality || 'N/A').toString().toLowerCase()] ?? -3;
                    let qB = qualityRank[(b.quality || 'N/A').toString().toLowerCase()] ?? -3;
                    if (qA !== qB) return qB - qA; // descending quality

                    const parseDate = (d) => {
                        if (!d || d === 'Unknown') return 0;
                        const parts = d.split('/');
                        if (parts.length === 3) return new Date(`${parts[2]}-${parts[1]}-${parts[0]}`).getTime();
                        return 0;
                    };
                    let dA = parseDate(a.date);
                    let dB = parseDate(b.date);
                    return dB - dA; // descending date
                }

                if (sortConfig.key === 'quality') {
                    valA = qualityRank[(valA || 'N/A').toString().toLowerCase()] ?? -3;
                    valB = qualityRank[(valB || 'N/A').toString().toLowerCase()] ?? -3;
                } else if (sortConfig.key === 'date') {
                    const parseDate = (d) => {
                        if (!d || d === 'Unknown') return 0;
                        const parts = d.split('/');
                        if (parts.length === 3) return new Date(`${parts[2]}-${parts[1]}-${parts[0]}`).getTime();
                        return 0;
                    };
                    valA = parseDate(valA);
                    valB = parseDate(valB);
                } else {
                    valA = (valA || '').toString().toLowerCase();
                    valB = (valB || '').toString().toLowerCase();
                }

                if (valA < valB) return sortConfig.direction === 'asc' ? -1 : 1;
                if (valA > valB) return sortConfig.direction === 'asc' ? 1 : -1;
                return 0;
            });
        }
        return filtered;
    }, [results, sortConfig, filters]);

    // Force strict auto sorting whenever results are updated
    useEffect(() => {
        setSortConfig({ key: 'auto', direction: 'desc' });
    }, [results]);

    // Handlers
    const handleSort = (key) => {
        let direction = 'asc';
        if (sortConfig.key === key && sortConfig.direction === 'asc') direction = 'desc';
        setSortConfig({ key, direction });
    };

    const toggleFilter = (colId, value) => {
        setFilters(prev => {
            const next = new Set(prev[colId]);
            if (next.has(value)) next.delete(value);
            else next.add(value);
            return { ...prev, [colId]: next };
        });
    };

    const clearFilters = (colId) => {
        setFilters(prev => ({ ...prev, [colId]: new Set() }));
    };

    // Drag to Reorder Columns - Disabled by user request

    const renderCell = (colId, r) => {
        switch (colId) {
            case 'cover':
                return r.poster && !imageErrors[r.id] ? (
                    <img
                        src={r.poster}
                        alt="poster"
                        style={{ width: '40px', height: '60px', objectFit: 'cover', borderRadius: '4px' }}
                        onError={() => setImageErrors(prev => ({ ...prev, [r.id]: true }))}
                    />
                ) : (
                    <div style={{ width: '40px', height: '60px', background: 'var(--glass-border)', borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
                        <ImageOff size={20} />
                    </div>
                );
            case 'title':
                return <a href={r.url} target="_blank" rel="noreferrer" style={{ color: 'var(--text-primary)', textDecoration: 'none', fontWeight: 500 }}>{r.title}</a>;
            case 'date':
                return <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{r.date || 'Unknown'}</span>;
            case 'quality': {
                const q = (r.quality || '').toLowerCase();
                let qClass = '';
                if (q === '2160p' || q === '4k') qClass = 'q-2160p';
                else if (q === '1080p' || q === '1080i') qClass = 'q-1080p';
                else if (q === '720p' || q === '720i') qClass = 'q-720p';
                else if (q === '576p' || q === '576i') qClass = 'q-576p';
                else if (q === '480p' || q === '480i') qClass = 'q-480p';
                return <span className={`quality-badge ${qClass}`}>{r.quality || 'SD'}</span>;
            }
            case 'metadata': {
                if (!r.metadata) return null;
                const { codec, audio, source, hdr } = r.metadata;
                return (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', justifyContent: 'center' }}>
                        {source && <span className="meta-badge source-badge">{source}</span>}
                        {codec && <span className="meta-badge codec-badge">{codec}</span>}
                        {audio && <span className="meta-badge audio-badge">{audio}</span>}
                        {hdr && <span className="meta-badge hdr-badge">{hdr}</span>}
                    </div>
                );
            }
            case 'site':
                return <span style={{ background: 'rgba(255,255,255,0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem', textTransform: 'capitalize', whiteSpace: 'nowrap', display: 'inline-block' }}>{r.site}</span>;
            case 'actions':
                if (fetchingLinksFor[r.id]) {
                    return (
                        <div style={{ textAlign: 'center', display: 'flex', justifyContent: 'center' }}>
                            <div style={{
                                width: '28px', height: '28px',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                animation: 'pulse-fetch 1.2s ease-in-out infinite',
                            }}>
                                <Download size={18} color="var(--accent-color)" />
                            </div>
                        </div>
                    );
                }

                if (!fetchedLinks[r.id]) {
                    return (
                        <div style={{ textAlign: 'center' }}>
                            <button
                                onClick={(e) => { e.stopPropagation(); onFetchLinks(r); }}
                                style={{
                                    background: 'var(--accent-color)', color: 'white', border: 'none',
                                    padding: '0.4rem 0.8rem', borderRadius: '6px', cursor: 'pointer',
                                    display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                                    fontWeight: 600, fontSize: '0.8rem', transition: 'all 0.2s'
                                }}
                            >
                                <Download size={14} /> Analyze
                            </button>
                        </div>
                    );
                }

                if (fetchedLinks[r.id].error) {
                    return <div style={{ textAlign: 'center', color: '#ef4444', fontSize: '0.8rem' }}>Error</div>;
                }

                const groups = groupLinks(fetchedLinks[r.id].links);
                const hosters = Object.keys(groups);

                if (hosters.length === 0) {
                    return <div style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>No links</div>;
                }

                return (
                    <div style={{ display: 'flex', gap: '6px', justifyContent: 'center', flexWrap: 'wrap', alignItems: 'center' }}>
                        {fetchedLinks[r.id].password && (
                            <button
                                title={`Password: ${fetchedLinks[r.id].password} (click to copy)`}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    navigator.clipboard.writeText(fetchedLinks[r.id].password);
                                    showToast(`Password copied: ${fetchedLinks[r.id].password}`);
                                }}
                                style={{
                                    background: 'rgba(250, 204, 21, 0.15)',
                                    border: '1px solid rgba(250, 204, 21, 0.3)',
                                    borderRadius: '8px',
                                    padding: '4px',
                                    cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    transition: 'all 0.2s',
                                    width: '28px', height: '28px',
                                }}
                                onMouseOver={e => e.currentTarget.style.background = 'rgba(250, 204, 21, 0.3)'}
                                onMouseOut={e => e.currentTarget.style.background = 'rgba(250, 204, 21, 0.15)'}
                            >
                                <KeyRound size={14} color="#facc15" />
                            </button>
                        )}
                        {hosters.map(h => {
                            return (
                                <button
                                    key={h}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        const allLinks = groups[h].join('\n');
                                        navigator.clipboard.writeText(allLinks);
                                        showToast(`${h} links copied to clipboard`);
                                    }}
                                    title={`Copy ${h} links (${groups[h].length})`}
                                    style={{
                                        background: 'rgba(255,255,255,0.05)',
                                        border: '1px solid rgba(255,255,255,0.1)',
                                        borderRadius: '8px',
                                        padding: '4px',
                                        cursor: 'pointer',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        transition: 'all 0.2s',
                                        width: '28px', height: '28px'
                                    }}
                                    onMouseOver={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.1)')}
                                    onMouseOut={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
                                >
                                    {(() => {
                                        const entry = HOSTER_ICONS[h];
                                        if (entry) {
                                            const { Icon, color } = entry;
                                            return <Icon size={16} color={color} />;
                                        }
                                        const color = stringToColor(h);
                                        return <Link2 size={16} color={color} style={{ filter: 'opacity(0.8)' }} />;
                                    })()}
                                </button>
                            );
                        })}
                        {/* Down arrow to toggle expanded view */}
                        <button
                            title="Toggle links list"
                            onClick={(e) => {
                                e.stopPropagation();
                                if (expandedId === r.id) {
                                    setExpandedId(null);
                                } else {
                                    setExpandedId(r.id);
                                    // Default to first hoster if none active
                                    if (!activeHoster[r.id]) {
                                        setActiveHoster(prev => ({ ...prev, [r.id]: hosters[0] }));
                                    }
                                }
                            }}
                            style={{
                                background: expandedId === r.id ? 'var(--accent-color)' : 'rgba(255,255,255,0.05)',
                                border: expandedId === r.id ? '1px solid var(--accent-color)' : '1px solid rgba(255,255,255,0.1)',
                                borderRadius: '8px',
                                padding: 0,
                                cursor: 'pointer',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                transition: 'all 0.2s',
                                width: '28px', height: '28px',
                                color: expandedId === r.id ? 'white' : 'var(--text-secondary)'
                            }}
                        >
                            <ChevronDown size={16} style={{ transform: expandedId === r.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                        </button>
                    </div>
                );
            default:
                return null;
        }
    };

    return (
        <>
            <div className="results-table-container animate-fade-in" style={{ overflow: 'visible' }}>
                <table className="results-table" style={{ position: 'relative' }}>
                    <thead>
                        <tr>
                            {columns.map(col => (
                                <th
                                    key={col.id}
                                    style={{ width: col.width, textAlign: (['cover', 'date', 'quality', 'metadata', 'site', 'actions'].includes(col.id) ? 'center' : 'left'), position: 'relative' }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: (['cover', 'date', 'quality', 'metadata', 'site', 'actions'].includes(col.id) ? 'center' : 'flex-start'), paddingRight: '0' }}>
                                        <span style={{ cursor: col.sortable ? 'pointer' : 'default', userSelect: 'none', display: 'flex', alignItems: 'center' }} onClick={() => col.sortable && handleSort(col.id)}>
                                            {col.label}
                                            {sortConfig.key === col.id && (
                                                <span style={{ marginLeft: '4px', fontSize: '0.8rem' }}>{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                                            )}
                                            {sortConfig.key === 'auto' && (col.id === 'quality' || col.id === 'date') && (
                                                <span style={{ marginLeft: '4px', fontSize: '0.8rem', opacity: 0.5 }}>↓</span>
                                            )}
                                        </span>
                                        {col.filterable && (
                                            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                                                <button
                                                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0', display: 'flex', alignItems: 'center', color: filters[col.id].size > 0 ? 'var(--accent-color)' : 'rgba(255,255,255,0.5)' }}
                                                    onClick={() => setActiveFilterMenu(activeFilterMenu === col.id ? null : col.id)}
                                                >
                                                    <Filter size={14} />
                                                </button>

                                                {activeFilterMenu === col.id && (
                                                    <div ref={filterMenuRef} className="filter-menu glass-panel" style={{ position: 'absolute', top: '100%', left: 0, zIndex: 100, padding: '0.5rem', borderRadius: '8px', minWidth: '150px', marginTop: '0.5rem', boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }}>
                                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '200px', overflowY: 'auto' }}>
                                                            {uniqueValues[col.id].map(val => (
                                                                <label key={val} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', cursor: 'pointer' }}>
                                                                    <input
                                                                        type="checkbox"
                                                                        checked={filters[col.id].has(val)}
                                                                        onChange={() => toggleFilter(col.id, val)}
                                                                    />
                                                                    <span style={{ textTransform: col.id === 'site' ? 'capitalize' : 'none' }}>{val}</span>
                                                                </label>
                                                            ))}
                                                        </div>
                                                        <div style={{ marginTop: '0.5rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '0.5rem', textAlign: 'center' }}>
                                                            <button onClick={() => clearFilters(col.id)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', fontSize: '0.8rem', cursor: 'pointer' }}>Clear Filters</button>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {processedResults.map((r) => (
                            <React.Fragment key={r.id}>
                                <tr className={expandedId === r.id ? 'expanded' : ''}>
                                    {columns.map(col => (
                                        <td key={`${r.id}-${col.id}`} style={{ textAlign: (['cover', 'date', 'quality', 'metadata', 'site', 'actions'].includes(col.id) ? 'center' : 'left') }}>
                                            {renderCell(col.id, r)}
                                        </td>
                                    ))}
                                </tr>
                                {/* Expanded Row for Links */}
                                {expandedId === r.id && fetchedLinks[r.id] && (
                                    <tr style={{ background: 'rgba(0,0,0,0.2)' }}>
                                        <td colSpan={columns.length} style={{ padding: '1.5rem', borderBottom: '1px solid var(--glass-border)' }}>
                                            <div className="animate-fade-in">
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                                                    {fetchedLinks[r.id].password && (
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(250, 204, 21, 0.1)', padding: '0.8rem', borderRadius: '8px', border: '1px solid rgba(250, 204, 21, 0.2)' }}>
                                                            <KeyRound size={18} color="#facc15" />
                                                            <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Password:</span>
                                                            <code style={{ background: 'rgba(255,255,255,0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px', color: '#facc15', fontWeight: 'bold' }}>{fetchedLinks[r.id].password}</code>
                                                            <button
                                                                onClick={() => {
                                                                    navigator.clipboard.writeText(fetchedLinks[r.id].password);
                                                                    showToast("Password copied");
                                                                }}
                                                                className="glass-button"
                                                                style={{
                                                                    marginLeft: 'auto',
                                                                    padding: '4px 12px',
                                                                    fontSize: '0.8rem',
                                                                    background: 'rgba(255,255,255,0.05)',
                                                                    border: '1px solid rgba(255,255,255,0.1)',
                                                                    borderRadius: '6px',
                                                                    color: 'var(--text-primary)',
                                                                    cursor: 'pointer',
                                                                    transition: 'all 0.2s'
                                                                }}
                                                                onMouseOver={(e) => e.target.style.background = 'rgba(255,255,255,0.1)'}
                                                                onMouseOut={(e) => e.target.style.background = 'rgba(255,255,255,0.05)'}
                                                            >
                                                                Copy
                                                            </button>
                                                        </div>
                                                    )}
                                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.5rem' }}>
                                                        {Object.entries(groupLinks(fetchedLinks[r.id].links)).map(([h, links]) => {
                                                            const entry = HOSTER_ICONS[h];
                                                            const { Icon, color } = entry || { Icon: Link2, color: stringToColor(h) };
                                                            return (
                                                                <div key={h} style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
                                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.8rem', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.5rem' }}>
                                                                        <Icon size={18} color={color} style={{ display: 'block' }} />
                                                                        <span style={{ fontWeight: 600, textTransform: 'lowercase', lineHeight: 1 }}>{h}</span>
                                                                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginLeft: 'auto', lineHeight: 1 }}>{links.length} links</span>
                                                                    </div>
                                                                    <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                                                                        {links.map((link, idx) => (
                                                                            <li key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                                                                                <div style={{ width: '4px', height: '4px', background: 'var(--accent-color)', borderRadius: '50%', marginTop: '0.6rem', flexShrink: 0 }}></div>
                                                                                <a href={link} target="_blank" rel="noreferrer" style={{ color: '#58a6ff', textDecoration: 'none', wordBreak: 'break-all', fontSize: '0.85rem', lineHeight: '1.4' }}>
                                                                                    {link}
                                                                                </a>
                                                                            </li>
                                                                        ))}
                                                                    </ul>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Ephemeral toast */}
            {toastMsg && (
                <div style={{
                    position: 'fixed', bottom: '2rem', left: '50%', transform: 'translateX(-50%)',
                    background: 'rgba(22, 27, 34, 0.95)', border: '1px solid rgba(34, 197, 94, 0.4)',
                    borderRadius: '12px', padding: '0.6rem 1.2rem',
                    display: 'flex', alignItems: 'center', gap: '0.5rem',
                    color: '#4ade80', fontSize: '0.9rem', fontWeight: 500,
                    boxShadow: '0 8px 30px rgba(0,0,0,0.4)', zIndex: 9999,
                    animation: 'toast-slide-up 0.3s ease-out',
                    backdropFilter: 'blur(10px)',
                }}>
                    <Check size={16} /> {toastMsg}
                </div>
            )}
        </>
    );
}
