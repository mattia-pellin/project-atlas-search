const API_BASE = 'http://localhost:8080/api';

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

export const fetchDownloadLinks = async (site, url) => {
    const res = await fetch(`${API_BASE}/links`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site, url })
    });
    if (!res.ok) throw new Error("Failed to fetch links");
    return res.json();
};

// SSE Connection manager
export class SearchStream {
    constructor(query, limit, onResults, onStatus, onDone, onError) {
        this.url = `${API_BASE}/search/stream?q=${encodeURIComponent(query)}&limit=${limit}`;
        this.es = new EventSource(this.url);

        this.es.addEventListener('results', (e) => {
            const data = JSON.parse(e.data);
            onResults(data.data);
        });

        this.es.addEventListener('status', (e) => {
            const data = JSON.parse(e.data);
            onStatus(data);
        });

        this.es.addEventListener('done', () => {
            onDone();
            this.close();
        });

        this.es.onerror = (e) => {
            console.error("SSE Error:", e);
            onError(e);
            this.close();
        };
    }

    close() {
        if (this.es) {
            this.es.close();
        }
    }
}
