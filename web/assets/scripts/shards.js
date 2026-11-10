(async () => {
    const grid = document.getElementById("shard-grid");
    const summary = document.getElementById("shards-summary");
    const updated = document.getElementById("shards-updated");
    if (!grid || !summary) return;

    const statusFor = (latency) => {
        if (latency === null || latency === undefined) return { label: "Offline", tone: "off" };
        if (latency > 250) return { label: "Degraded", tone: "warn" };
        return { label: "Online", tone: "ok" };
    };

    const render = (payload) => {
        const shards = Array.isArray(payload.shards) ? payload.shards : [];

        if (!shards.length) {
            summary.textContent = "No shards are reporting in right now.";
            grid.replaceChildren();
            return;
        }

        const totalGuilds = shards.reduce((sum, shard) => sum + (shard.guilds ?? 0), 0);
        summary.textContent = shards.length === 1
            ? `1 shard, ${totalGuilds} server${totalGuilds === 1 ? "" : "s"}.`
            : `${shards.length} shards, ${totalGuilds} servers total.`;

        grid.replaceChildren(...shards.map((shard) => {
            const { label, tone } = statusFor(shard.latency);

            const card = document.createElement("article");
            card.className = "card shard-card";

            const heading = document.createElement("h3");
            heading.textContent = `Shard ${shard.id}`;
            card.append(heading);

            const statusLine = document.createElement("p");
            statusLine.className = "shard-stat";
            const dot = document.createElement("span");
            dot.className = `dot dot-${tone}`;
            statusLine.append(dot, document.createTextNode(label));
            card.append(statusLine);

            const guildsLine = document.createElement("p");
            guildsLine.className = "shard-stat";
            guildsLine.textContent = `${shard.guilds ?? 0} server${shard.guilds === 1 ? "" : "s"}`;
            card.append(guildsLine);

            const latencyLine = document.createElement("p");
            latencyLine.className = "shard-stat";
            latencyLine.textContent = typeof shard.latency === "number"
                ? `${shard.latency}ms latency`
                : "latency unknown";
            card.append(latencyLine);

            return card;
        }));
    };

    const load = async () => {
        try {
            const response = await fetch("/api/shards", { cache: "no-store" });
            if (!response.ok) throw new Error(`status ${response.status}`);
            render(await response.json());
            updated.textContent = `Last updated ${new Date().toLocaleTimeString()}.`;
            updated.hidden = false;
        } catch {
            summary.textContent = "Could not reach the workshop. Retrying shortly.";
        }
    };

    await load();
    setInterval(load, 30000);
})();
