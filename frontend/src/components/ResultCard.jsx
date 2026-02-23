import React, { useState } from 'react';
import { Download, Loader2, Link as LinkIcon, Lock } from 'lucide-react';
import { fetchDownloadLinks } from '../lib/api';

export default function ResultCard({ result }) {
    const [loading, setLoading] = useState(false);
    const [linksInfo, setLinksInfo] = useState(null);
    const [error, setError] = useState(null);

    const handleFetch = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchDownloadLinks(result.site, result.url);
            setLinksInfo(data);
        } catch (e) {
            setError("Failed to fetch links. Ensure credentials are correct.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="glass-panel animate-fade-in result-card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {result.poster && (
                <div style={{ height: '200px', width: '100%', overflow: 'hidden' }}>
                    <img src={result.poster} alt="Poster" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
            )}

            <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', flex: 1, gap: '0.5rem' }}>
                <h3 style={{ fontSize: '1.1rem', margin: 0, lineHeight: 1.3 }} title={result.title}>
                    {result.title}
                </h3>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 'auto' }}>
                    <span style={{ background: 'rgba(255,255,255,0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>{result.quality}</span>
                    <span>{result.site}</span>
                    <span>{result.date !== 'Unknown' ? result.date : ''}</span>
                </div>

                {/* Action Area */}
                <div style={{ marginTop: '1rem', borderTop: '1px solid var(--glass-border)', paddingTop: '1rem' }}>
                    {!linksInfo ? (
                        <button
                            onClick={handleFetch}
                            disabled={loading}
                            style={{
                                width: '100%', background: 'var(--accent-color)', color: 'white', border: 'none',
                                borderRadius: '8px', padding: '0.5rem', cursor: loading ? 'not-allowed' : 'pointer',
                                display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', fontWeight: 600,
                                opacity: loading ? 0.7 : 1
                            }}
                        >
                            {loading ? <Loader2 className="animate-spin" size={18} /> : <Download size={18} />}
                            Fetch Download Links
                        </button>
                    ) : (
                        <div style={{ fontSize: '0.9rem' }}>
                            <h4 style={{ margin: '0 0 0.5rem 0', display: 'flex', alignItems: 'center', gap: '0.3rem' }}><LinkIcon size={14} /> Download Links:</h4>
                            {linksInfo.links.length > 0 ? (
                                <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                                    {linksInfo.links.map((link, idx) => (
                                        <li key={idx}><a href={link} target="_blank" rel="noopener noreferrer" style={{ wordBreak: 'break-all' }}>{link.split('/').pop()}</a></li>
                                    ))}
                                </ul>
                            ) : (
                                <p style={{ margin: 0, color: 'var(--text-secondary)' }}>No links found.</p>
                            )}

                            {linksInfo.password && (
                                <div style={{ marginTop: '0.8rem', background: 'rgba(0,0,0,0.3)', padding: '0.5rem', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Lock size={14} color="var(--accent-color)" />
                                    <span>Password: <strong style={{ color: 'white' }}>{linksInfo.password}</strong></span>
                                </div>
                            )}
                        </div>
                    )}

                    {error && <p style={{ color: 'var(--danger-color)', fontSize: '0.85rem', margin: '0.5rem 0 0 0' }}>{error}</p>}
                </div>
            </div>
        </div>
    );
}
