import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "";

export default function App() {
  const [input, setInput] = useState("214328887, 107830991");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function request(url) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(url);
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
      setRows(body.results);
    } catch (e) {
      setError(e.message);
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  function showAll() {
    request(`${API_BASE}/sample?limit=100`);
  }

  async function lookup() {
    const ids = input
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    if (ids.length === 0) {
      setError("Enter at least one user ID.");
      return;
    }
    if (!ids.every((id) => /^\d+$/.test(id))) {
      setError("User IDs must be numeric.");
      return;
    }

    request(`${API_BASE}/users?ids=${ids.join(",")}`);
  }

  return (
    <main className="wrap">
      <h1>Twitter follower and followee counts</h1>

      <div className="controls">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && lookup()}
          placeholder="User IDs, comma separated"
          aria-label="User IDs"
        />
        <button onClick={lookup} disabled={loading}>
          {loading ? "Loading" : "Look up"}
        </button>
        <button className="secondary" onClick={showAll} disabled={loading}>
          All users
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {rows.length > 0 && (
        <section className="results">
          {rows.map((r) =>
            r.error ? (
              <p key={r.user_id} className="miss">
                {r.user_id} was not found in the dataset
              </p>
            ) : (
              <div key={r.user_id} className="user">
                <p>
                  {r.user_id} has <span className="count">{r.followers}</span>{" "}
                  followers
                </p>
                <p>
                  {r.user_id} has <span className="count">{r.followees}</span>{" "}
                  followees
                </p>
              </div>
            )
          )}
        </section>
      )}
    </main>
  );
}
