(async () => {
    const box = document.getElementById("status");
    const text = document.getElementById("status-text");
    if (!box || !text) return;

    const duration = (seconds) => {
        const d = Math.floor(seconds / 86400);
        const h = Math.floor((seconds % 86400) / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        if (d) return `${d}d ${h}h`;
        if (h) return `${h}h ${m}m`;
        return `${m}m`;
    };

    try {
        const response = await fetch("/api/status", { cache: "no-store" });
        if (!response.ok) return;
        const status = await response.json();

        const parts = ["Workshop online"];
        if (status.version) parts.push(`v${status.version}`);
        if (typeof status.uptime === "number") parts.push(`up ${duration(status.uptime)}`);
        if (typeof status.servers === "number") {
            parts.push(`${status.servers} server${status.servers === 1 ? "" : "s"}`);
        }

        text.textContent = parts.join(" · ");
        box.hidden = false;
    } catch {
        /* the page reads fine without it */
    }
})();