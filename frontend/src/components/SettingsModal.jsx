import React, { useState, useEffect } from 'react';
import { fetchSettings, updateSettings, clearCache } from '../lib/api';
import { Save, X, Loader2, CheckCircle2, AlertCircle, ChevronDown, ChevronRight, Trash2, Check } from 'lucide-react';

const SUPPORTED_SITES = [
    'HDItalia', 'Lost Planet', 'LFI', 'HD4ME', '1337x'
];

const DEFAULT_URLS = {
    'HDItalia': 'https://www.hditaliabits.online',
    'Lost Planet': 'https://lostplanet.online',
    'LFI': 'http://laforestaincantata.org',
    'HD4ME': 'https://hd4me.net',
    '1337x': 'https://1337x.to'
};

export default function SettingsModal({ onClose }) {
    const [maxResults, setMaxResults] = useState(10);
    const [dnsList, setDnsList] = useState([]);
    const [dnsInput, setDnsInput] = useState("");
    const [credentials, setCredentials] = useState({});
    const [expandedSites, setExpandedSites] = useState({});
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    const [showAllDns, setShowAllDns] = useState(false);

    // New Cache Settings
    const [cacheEnabled, setCacheEnabled] = useState(true);
    const [cacheTtl, setCacheTtl] = useState(60);
    const [clearingCache, setClearingCache] = useState(false);
    const [cacheMessage, setCacheMessage] = useState('');

    const isValidIpv4 = (ip) => {
        const ipv4Regex = /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
        return ipv4Regex.test(ip.trim());
    };

    useEffect(() => {
        fetchSettings().then(data => {
            setMaxResults(data.max_results);
            if (data.dns_servers && data.dns_servers !== 'system') {
                setDnsList(data.dns_servers.split(',').map(s => s.trim()).filter(Boolean));
            } else {
                setDnsList([]);
            }
            if (data.cache_enabled !== undefined) setCacheEnabled(data.cache_enabled);
            if (data.cache_ttl_minutes !== undefined) setCacheTtl(data.cache_ttl_minutes);

            const credsMap = {};

            // Initialize default structure
            SUPPORTED_SITES.forEach(site => {
                credsMap[site] = { username: '', password: '', custom_name: '', custom_url: '', is_enabled: true };
            });

            data.credentials.forEach(c => {
                if (credsMap[c.site_key]) {
                    credsMap[c.site_key] = { ...credsMap[c.site_key], ...c };
                }
            });
            setCredentials(credsMap);
            setLoading(false);
        }).catch(console.error);
    }, []);

    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onClose]);

    const handleDnsKeyDown = (e) => {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            const val = dnsInput.trim().replace(/,/g, '');
            if (val && !dnsList.includes(val)) {
                setDnsList([...dnsList, val]);
            }
            setDnsInput("");
        }
    };

    const removeDns = (index) => {
        setDnsList(dnsList.filter((_, i) => i !== index));
    };

    const toggleSiteExpand = (site) => {
        setExpandedSites(prev => ({ ...prev, [site]: !prev[site] }));
    };

    const handleSave = async (e) => {
        e.preventDefault();
        const hasInvalid = dnsList.some(ip => !isValidIpv4(ip));
        if (hasInvalid) {
            alert("Please remove any invalid entries from Custom DNS Servers first.");
            return;
        }
        setSaving(true);

        const credsList = SUPPORTED_SITES.map(site => ({
            site_key: site,
            username: credentials[site]?.username || '',
            password: credentials[site]?.password || '',
            custom_name: credentials[site]?.custom_name || '',
            custom_url: credentials[site]?.custom_url || '',
            is_enabled: credentials[site]?.is_enabled !== false
        }));

        try {
            const finalDns = dnsList.length === 0 ? 'system' : dnsList.join(',');
            await updateSettings({
                max_results: parseInt(maxResults),
                dns_servers: finalDns,
                cache_enabled: cacheEnabled,
                cache_ttl_minutes: parseInt(cacheTtl) || 60,
                credentials: credsList
            });
            onClose();
        } catch (e) {
            console.error(e);
            alert("Failed to save settings");
        } finally {
            setSaving(false);
        }
    };

    const handleClearCache = async () => {
        setClearingCache(true);
        setCacheMessage('');
        try {
            await clearCache();
            setCacheMessage('Cache cleared!');
            setTimeout(() => setCacheMessage(''), 3000);
        } catch (e) {
            console.error(e);
            setCacheMessage('Failed to clear');
        } finally {
            setClearingCache(false);
        }
    };

    const handleCredChange = (site, field, value) => {
        setCredentials(prev => ({
            ...prev,
            [site]: { ...prev[site], [field]: value }
        }));
    };

    if (loading) return (
        <div className="modal-overlay">
            <div className="modal-content glass-panel" style={{ display: 'flex', justifyContent: 'center' }}>
                <Loader2 className="animate-spin" size={32} />
            </div>
        </div>
    );

    return (
        <div className="modal-overlay" style={{ backdropFilter: 'blur(10px)', backgroundColor: 'rgba(0, 0, 0, 0.6)' }}>
            <div className="modal-content animate-fade-in" style={{
                background: 'rgba(15, 23, 42, 0.85)',
                backdropFilter: 'blur(20px)',
                borderRadius: '16px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
                width: '100%',
                maxWidth: '850px',
                padding: '2rem',
                color: 'white'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div style={{ background: 'var(--accent-color)', padding: '0.5rem', borderRadius: '8px', display: 'flex' }}>
                            <Save size={20} color="white" />
                        </div>
                        <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600 }}>Settings</h2>
                    </div>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.6)', cursor: 'pointer', transition: 'color 0.2s' }} onMouseOver={e => e.currentTarget.style.color = 'white'} onMouseOut={e => e.currentTarget.style.color = 'rgba(255,255,255,0.6)'}>
                        <X size={24} />
                    </button>
                </div>

                <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                    {/* GLOBAL SETTINGS */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', background: 'rgba(0,0,0,0.2)', padding: '1.5rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>

                        {/* Max Results */}
                        <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.8rem' }}>
                                <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Max Results per Engine</label>
                                <span style={{ fontSize: '1rem', color: 'var(--accent-color)', fontWeight: 600 }}>{maxResults}</span>
                            </div>
                            <input
                                type="range"
                                min="1"
                                max="100"
                                step="1"
                                list="max-results-markers"
                                value={maxResults}
                                onChange={e => setMaxResults(e.target.value)}
                                style={{ width: '100%', accentColor: 'var(--accent-color)', cursor: 'pointer' }}
                            />
                            <datalist id="max-results-markers" style={{ display: 'flex', justifyContent: 'space-between', color: 'rgba(255,255,255,0.4)', fontSize: '0.7rem', marginTop: '0.4rem' }}>
                                <option value="1" label="1"></option>
                                <option value="25" label="25"></option>
                                <option value="50" label="50"></option>
                                <option value="75" label="75"></option>
                                <option value="100" label="100"></option>
                            </datalist>
                        </div>

                        {/* Search Cache */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                            <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Search Cache</label>

                            <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
                                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', gap: '0.5rem' }} onClick={e => e.stopPropagation()}>
                                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: cacheEnabled ? 'var(--accent-color)' : 'var(--text-secondary)' }}>{cacheEnabled ? 'ON' : 'OFF'}</span>
                                    <div style={{
                                        position: 'relative', width: '40px', height: '22px',
                                        background: cacheEnabled ? 'var(--accent-color)' : 'rgba(255,255,255,0.2)',
                                        borderRadius: '20px', transition: 'background 0.3s'
                                    }}>
                                        <div style={{
                                            position: 'absolute', top: '2px', left: cacheEnabled ? '20px' : '2px',
                                            width: '18px', height: '18px', background: 'white',
                                            borderRadius: '50%', transition: 'left 0.3s ease',
                                            boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                                        }}></div>
                                    </div>
                                    <input
                                        type="checkbox"
                                        checked={cacheEnabled}
                                        onChange={e => setCacheEnabled(e.target.checked)}
                                        style={{ display: 'none' }}
                                    />
                                </label>

                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <input
                                        type="number"
                                        min="0"
                                        max="1440"
                                        value={cacheTtl}
                                        onChange={e => setCacheTtl(e.target.value)}
                                        disabled={!cacheEnabled}
                                        style={{
                                            width: '60px', padding: '0.3rem 0.5rem', borderRadius: '6px',
                                            border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.3)',
                                            color: 'white', outline: 'none', opacity: cacheEnabled ? 1 : 0.5,
                                            fontSize: '0.9rem', fontWeight: 500, textAlign: 'center'
                                        }}
                                    />
                                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', opacity: cacheEnabled ? 1 : 0.5 }}>mins TTL</span>
                                </div>

                                {/* Empty Cache Action */}
                                <button
                                    type="button"
                                    onClick={handleClearCache}
                                    disabled={clearingCache}
                                    style={{
                                        display: 'flex', alignItems: 'center', gap: '0.4rem',
                                        padding: '0.3rem 0.8rem', borderRadius: '6px',
                                        border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.1)',
                                        color: '#ef4444', fontSize: '0.8rem', fontWeight: 600,
                                        cursor: clearingCache ? 'not-allowed' : 'pointer', transition: 'all 0.2s', opacity: clearingCache ? 0.7 : 1
                                    }}
                                    title="Empty Cache Database"
                                >
                                    {clearingCache ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                                    {cacheMessage ? (cacheMessage.includes('Failed') ? 'Error' : 'Cleared!') : 'Empty Cache'}
                                </button>
                            </div>
                        </div>

                        {/* Custom DNS */}
                        <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '0.5rem' }}>
                                <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Custom DNS Servers</label>
                                <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)' }}>Press Enter to add</span>
                            </div>

                            <div style={{
                                display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center',
                                padding: '0.5rem 0.75rem', borderRadius: '8px',
                                border: '1px solid rgba(255,255,255,0.15)',
                                background: 'rgba(0,0,0,0.3)', minHeight: '46px',
                                transition: 'all 0.2s'
                            }} onClick={() => document.getElementById('dns-input-field').focus()}>

                                {dnsList.slice(0, showAllDns ? dnsList.length : 3).map((ip, i) => {
                                    const valid = isValidIpv4(ip);
                                    return (
                                        <div key={i} style={{
                                            display: 'flex', alignItems: 'center', gap: '0.4rem',
                                            padding: '0.2rem 0.6rem', borderRadius: '20px',
                                            background: 'rgba(255,255,255,0.1)', color: 'white',
                                            fontSize: '0.85rem', border: `1px solid ${valid ? 'rgba(255,255,255,0.2)' : 'rgba(239,68,68,0.5)'}`
                                        }}>
                                            <span>{ip}</span>
                                            {valid ? <CheckCircle2 size={13} color="var(--success-color)" /> : <AlertCircle size={13} color="#ef4444" />}
                                            <X size={13} style={{ cursor: 'pointer', opacity: 0.6 }} onClick={(e) => { e.stopPropagation(); removeDns(i); }} onMouseOver={e => e.currentTarget.style.opacity = 1} onMouseOut={e => e.currentTarget.style.opacity = 0.6} />
                                        </div>
                                    )
                                })}

                                {!showAllDns && dnsList.length > 3 && (
                                    <div
                                        onClick={(e) => { e.stopPropagation(); setShowAllDns(true); }}
                                        style={{
                                            padding: '0.2rem 0.6rem', borderRadius: '20px',
                                            background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', cursor: 'pointer',
                                            fontSize: '0.8rem', fontWeight: 600, border: '1px solid rgba(59, 130, 246, 0.3)'
                                        }}
                                    >
                                        +{dnsList.length - 3} more
                                    </div>
                                )}

                                <input
                                    id="dns-input-field"
                                    type="text"
                                    value={dnsInput}
                                    onChange={e => setDnsInput(e.target.value)}
                                    onKeyDown={handleDnsKeyDown}
                                    placeholder={dnsList.length === 0 ? "System Default" : "Add IP..."}
                                    style={{
                                        flex: '1 1 auto', border: 'none', background: 'transparent',
                                        color: 'white', minWidth: '100px', outline: 'none',
                                        fontSize: '0.9rem', padding: '0.2rem'
                                    }}
                                    onFocus={() => setShowAllDns(true)}
                                    onBlur={() => setTimeout(() => setShowAllDns(false), 200)}
                                />
                            </div>
                        </div>
                    </div>

                    {/* SEARCH ENGINES */}
                    <div>
                        <h3 style={{ fontSize: '1.2rem', fontWeight: 500, marginBottom: '1rem', color: 'white' }}>Search Engines</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            {SUPPORTED_SITES.map(site => {
                                const isEnabled = credentials[site]?.is_enabled !== false;
                                const isExpanded = expandedSites[site];

                                return (
                                    <div key={site} style={{
                                        background: isEnabled ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.2)',
                                        border: isEnabled ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(255,255,255,0.05)',
                                        borderRadius: '12px',
                                        transition: 'all 0.3s ease',
                                        overflow: 'hidden'
                                    }}>
                                        <div style={{
                                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                            padding: '1.25rem', opacity: isEnabled ? 1 : 0.6, cursor: 'pointer'
                                        }} onClick={() => toggleSiteExpand(site)}>
                                            <div style={{ display: 'flex', alignItems: 'center', justifyItems: 'center', gap: '0.5rem' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', paddingTop: '2px' }}>
                                                    {isExpanded ? <ChevronDown size={18} color="rgba(255,255,255,0.5)" /> : <ChevronRight size={18} color="rgba(255,255,255,0.5)" />}
                                                </div>
                                                <h4 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, userSelect: 'none', lineHeight: 1 }}>{site}</h4>
                                            </div>

                                            {/* Custom Toggle Switch */}
                                            <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', gap: '0.5rem' }} onClick={e => e.stopPropagation()}>
                                                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: isEnabled ? 'var(--accent-color)' : 'var(--text-secondary)' }}>{isEnabled ? 'ON' : 'OFF'}</span>
                                                <div style={{
                                                    position: 'relative', width: '40px', height: '22px',
                                                    background: isEnabled ? 'var(--accent-color)' : 'rgba(255,255,255,0.2)',
                                                    borderRadius: '20px', transition: 'background 0.3s'
                                                }}>
                                                    <div style={{
                                                        position: 'absolute', top: '2px', left: isEnabled ? '20px' : '2px',
                                                        width: '18px', height: '18px', background: 'white',
                                                        borderRadius: '50%', transition: 'left 0.3s ease',
                                                        boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                                                    }}></div>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={isEnabled}
                                                    onChange={e => handleCredChange(site, 'is_enabled', e.target.checked)}
                                                    style={{ display: 'none' }}
                                                />
                                            </label>
                                        </div>

                                        {isExpanded && (
                                            <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', padding: '1.25rem' }}>
                                                <div style={{ display: 'grid', gridTemplateColumns: (site !== '1337x' && site !== 'HD4ME') ? '1fr 1fr 1.5fr' : '1fr', gap: '1rem' }}>
                                                    {site !== '1337x' && site !== 'HD4ME' && (
                                                        <>
                                                            <div>
                                                                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>Username</label>
                                                                <input
                                                                    type="text"
                                                                    placeholder="User/Email"
                                                                    value={credentials[site]?.username || ''}
                                                                    onChange={e => handleCredChange(site, 'username', e.target.value)}
                                                                    style={{ padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.03)', color: 'white', width: '100%', fontSize: '0.9rem', outline: 'none' }}
                                                                />
                                                            </div>
                                                            <div>
                                                                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>Password</label>
                                                                <input
                                                                    type="password"
                                                                    placeholder="Password"
                                                                    value={credentials[site]?.password || ''}
                                                                    onChange={e => handleCredChange(site, 'password', e.target.value)}
                                                                    style={{ padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.03)', color: 'white', width: '100%', fontSize: '0.9rem', outline: 'none' }}
                                                                />
                                                            </div>
                                                        </>
                                                    )}
                                                    <div>
                                                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>Base URL</label>
                                                        <input
                                                            type="url"
                                                            placeholder={DEFAULT_URLS[site]}
                                                            value={credentials[site]?.custom_url || ''}
                                                            onChange={e => handleCredChange(site, 'custom_url', e.target.value)}
                                                            style={{ padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.03)', color: 'white', width: '100%', fontSize: '0.9rem', outline: 'none' }}
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginTop: '1rem' }}>
                        <button type="button" onClick={onClose} style={{
                            padding: '0.75rem 2rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)',
                            background: 'transparent', color: 'white', fontWeight: 600, cursor: 'pointer',
                            transition: 'all 0.2s'
                        }} onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'} onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
                            Cancel
                        </button>
                        <button type="submit" disabled={saving} style={{
                            padding: '0.75rem 2rem', borderRadius: '8px', border: 'none',
                            background: 'var(--accent-color)', color: 'white', fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer',
                            opacity: saving ? 0.6 : 1, display: 'flex', alignItems: 'center', gap: '0.5rem',
                            transition: 'opacity 0.2s', boxShadow: '0 4px 14px rgba(0, 112, 243, 0.4)'
                        }}>
                            {saving ? <Loader2 className="animate-spin" size={18} /> : null}
                            Save Changes
                        </button>
                    </div>
                </form>
            </div >
        </div >
    );
}
