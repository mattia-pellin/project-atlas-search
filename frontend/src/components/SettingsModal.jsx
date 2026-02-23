import React, { useState, useEffect } from 'react';
import { fetchSettings, updateSettings } from '../lib/api';
import { Save, X, Loader2 } from 'lucide-react';

const SUPPORTED_SITES = [
    'hditaliabits', 'lostplanet', 'laforestaincantata', 'hd4me', '1337x'
];

export default function SettingsModal({ onClose }) {
    const [maxResults, setMaxResults] = useState(10);
    const [credentials, setCredentials] = useState({});
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        fetchSettings().then(data => {
            setMaxResults(data.max_results);
            const credsMap = {};

            // Initialize default structure
            SUPPORTED_SITES.forEach(site => {
                credsMap[site] = { username: '', password: '', custom_name: '', is_enabled: true };
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

    const handleSave = async (e) => {
        e.preventDefault();
        setSaving(true);

        const credsList = SUPPORTED_SITES.map(site => ({
            site_key: site,
            username: credentials[site]?.username || '',
            password: credentials[site]?.password || '',
            custom_name: credentials[site]?.custom_name || '',
            is_enabled: credentials[site]?.is_enabled !== false
        }));

        try {
            await updateSettings({ max_results: parseInt(maxResults), credentials: credsList });
            onClose();
        } catch (e) {
            console.error(e);
            alert("Failed to save settings");
        } finally {
            setSaving(false);
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
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
            <div className="modal-content glass-panel animate-fade-in" style={{ maxWidth: '800px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                    <h2 style={{ margin: 0 }}>Settings</h2>
                    <button onClick={onClose} className="settings-btn"><X size={24} /></button>
                </div>

                <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>Max Results per Site</label>
                        <input
                            type="number"
                            value={maxResults}
                            onChange={e => setMaxResults(e.target.value)}
                            style={{ padding: '0.5rem', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(0,0,0,0.2)', color: 'white', width: '100px' }}
                        />
                    </div>

                    <div>
                        <h3 style={{ borderBottom: '1px solid var(--glass-border)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>Site Configuration</h3>
                        <div style={{ display: 'grid', gap: '1rem' }}>
                            {SUPPORTED_SITES.map(site => (
                                <div key={site} style={{ background: credentials[site]?.is_enabled === false ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.05)', padding: '1rem', borderRadius: '8px', opacity: credentials[site]?.is_enabled === false ? 0.6 : 1, transition: 'all 0.2s' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem' }}>
                                        <h4 style={{ textTransform: 'capitalize', margin: 0 }}>{site}</h4>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
                                            <input
                                                type="checkbox"
                                                checked={credentials[site]?.is_enabled !== false}
                                                onChange={e => handleCredChange(site, 'is_enabled', e.target.checked)}
                                                style={{ width: '16px', height: '16px', accentColor: 'var(--accent-color)' }}
                                            />
                                            Enable Site
                                        </label>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                                        <input
                                            type="text"
                                            placeholder="Custom Display Name (Optional)"
                                            value={credentials[site]?.custom_name || ''}
                                            onChange={e => handleCredChange(site, 'custom_name', e.target.value)}
                                            style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--glass-border)', background: 'rgba(0,0,0,0.2)', color: 'white' }}
                                            disabled={credentials[site]?.is_enabled === false}
                                        />
                                        {site !== '1337x' && (
                                            <>
                                                <input
                                                    type="text"
                                                    placeholder="Username / Email"
                                                    value={credentials[site]?.username || ''}
                                                    onChange={e => handleCredChange(site, 'username', e.target.value)}
                                                    style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--glass-border)', background: 'rgba(0,0,0,0.2)', color: 'white' }}
                                                    disabled={credentials[site]?.is_enabled === false}
                                                />
                                                <input
                                                    type="password"
                                                    placeholder="Password"
                                                    value={credentials[site]?.password || ''}
                                                    onChange={e => handleCredChange(site, 'password', e.target.value)}
                                                    style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--glass-border)', background: 'rgba(0,0,0,0.2)', color: 'white' }}
                                                    disabled={credentials[site]?.is_enabled === false}
                                                />
                                            </>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={saving}
                        style={{
                            background: 'var(--success-color)', color: 'white', border: 'none',
                            borderRadius: '8px', padding: '0.75rem', fontWeight: 600,
                            display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem',
                            cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1,
                            marginTop: '1rem'
                        }}>
                        {saving ? <Loader2 className="animate-spin" size={20} /> : <Save size={20} />}
                        Save Configurations
                    </button>
                </form>
            </div>
        </div>
    );
}
