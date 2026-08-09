"use client";

import { useEffect, useState } from "react";
import { api, ConfigInfo } from "@/lib/api";

export default function ConfigPage() {
  const [config, setConfig] = useState<ConfigInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);

  function load() {
    api.getConfig().then(setConfig).catch((e) => setError(String(e)));
  }

  useEffect(load, []);

  async function switchMode(mode: "daily" | "weekly") {
    setSwitching(true);
    try {
      await api.setMode(mode);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div>
      <h2>Configuration</h2>
      {error && <p className="error">{error}</p>}
      {config && (
        <>
          <div className="card-grid">
            <div className="card">
              <div className="label">Digest mode</div>
              <div className="value" style={{ fontSize: 20 }}>{config.digest_mode}</div>
            </div>
            <div className="card">
              <div className="label">RSS sources</div>
              <div className="value">{config.feed_count}</div>
            </div>
            <div className="card">
              <div className="label">Stories per digest</div>
              <div className="value">{config.top_n_stories}</div>
            </div>
            <div className="card">
              <div className="label">Lookback window</div>
              <div className="value" style={{ fontSize: 20 }}>{config.lookback_hours}h</div>
            </div>
          </div>

          <h3>Switch digest mode</h3>
          <p style={{ color: "var(--muted)" }}>
            Weekly mode widens the lookback to 7 days and applies the Editor Agent&apos;s
            stricter &quot;Best of&quot; curation bar. Takes effect on the next pipeline run.
          </p>
          <div className="mode-toggle">
            <button
              className={config.digest_mode === "daily" ? "" : "secondary"}
              disabled={switching || config.digest_mode === "daily"}
              onClick={() => switchMode("daily")}
            >
              Daily
            </button>
            <button
              className={config.digest_mode === "weekly" ? "" : "secondary"}
              disabled={switching || config.digest_mode === "weekly"}
              onClick={() => switchMode("weekly")}
            >
              Weekly
            </button>
          </div>
        </>
      )}
    </div>
  );
}
