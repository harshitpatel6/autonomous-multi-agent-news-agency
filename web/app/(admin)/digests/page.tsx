"use client";

import { useEffect, useState } from "react";
import { api, DigestSummary } from "@/lib/api";

export default function DigestsPage() {
  const [digests, setDigests] = useState<DigestSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDigests().then(setDigests).catch((e) => setError(String(e)));
  }, []);

  return (
    <div>
      <h2>Recent Digests</h2>
      {error && <p className="error">{error}</p>}
      <table>
        <thead>
          <tr><th>Digest ID</th><th>Stories</th><th>Sent At</th></tr>
        </thead>
        <tbody>
          {digests?.map((d) => (
            <tr key={d.digest_id}>
              <td>{d.digest_id}</td>
              <td>{d.story_count}</td>
              <td>{d.sent_at ? new Date(d.sent_at).toLocaleString() : "—"}</td>
            </tr>
          ))}
          {digests && digests.length === 0 && <tr><td colSpan={3}>No digests sent yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
