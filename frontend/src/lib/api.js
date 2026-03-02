export const API_BASE = '/api';

export const fetchSettings = async () => {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) throw new Error("Failed to fetch settings");
    return res.json();
};

export const updateSettings = async (data) => {
    const res = await fetch(`${API_BASE}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error("Failed to update settings");
    return res.json();
};

export const clearCache = async () => {
    const res = await fetch(`${API_BASE}/cache`, {
        method: "DELETE"
    });
    if (!res.ok) throw new Error("Failed to clear cache");
    return res.json();
};

export const fetchDownloadLinks = async (site, url) => {
    const res = await fetch(`${API_BASE}/links`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site, url })
    });
    if (!res.ok) throw new Error("Failed to fetch links");
    return res.json();
};

export const sendToQBittorrent = async (links) => {
    const res = await fetch(`${API_BASE}/integrations/qbittorrent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ links })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to send to qBittorrent");
    return data;
};

export const sendToJDownloader = async (links, password, packageName) => {
    const res = await fetch(`${API_BASE}/integrations/jdownloader`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ links, password, package_name: packageName })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to send to JDownloader");
    return data;
};
