// src/App.jsx
import { useEffect, useRef, useState } from "react";
import { getBalance, getPrices, login, placeTrade } from "./api";

// ── Tiny helpers ──────────────────────────────────────────────────────────────
const fmt = (n) =>
  Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const cls = (...c) => c.filter(Boolean).join(" ");

// ── Login Page ────────────────────────────────────────────────────────────────
function LoginPage({ onLogin }) {
  const [form, setForm]     = useState({ username: "demo", password: "demo123" });
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);

  const handle = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      const { data } = await login(form.username, form.password);
      localStorage.setItem("token", data.access_token);
      onLogin();
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="login-root">
      <div className="login-card">
        <div className="login-brand">
          <span className="brand-hex">◈</span>
          <h1>PORTFOLIO<br />TRACKER</h1>
          <p className="brand-sub">Binance Futures Testnet</p>
        </div>
        <form onSubmit={handle} className="login-form">
          <div className="field">
            <label>USERNAME</label>
            <input value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              placeholder="demo" autoFocus />
          </div>
          <div className="field">
            <label>PASSWORD</label>
            <input type="password" value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="••••••••" />
          </div>
          {error && <p className="err-msg">{error}</p>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "CONNECTING…" : "ENTER DASHBOARD →"}
          </button>
        </form>
        <p className="login-hint">Default: demo / demo123</p>
      </div>
    </div>
  );
}

// ── Price Card ─────────────────────────────────────────────────────────────────
function PriceCard({ symbol, price, prev }) {
  const up   = prev && parseFloat(price) >= parseFloat(prev);
  const down = prev && parseFloat(price) <  parseFloat(prev);
  return (
    <div className={cls("price-card", up && "tick-up", down && "tick-down")}>
      <span className="price-symbol">{symbol.replace("USDT", "")}<span>/USDT</span></span>
      <span className="price-val">${fmt(price)}</span>
      {prev && (
        <span className={cls("price-delta", up ? "green" : "red")}>
          {up ? "▲" : "▼"}{" "}
          {Math.abs(((parseFloat(price) - parseFloat(prev)) / parseFloat(prev)) * 100).toFixed(3)}%
        </span>
      )}
    </div>
  );
}

// ── Trade Panel ───────────────────────────────────────────────────────────────
function TradePanel({ onTrade }) {
  const [form, setForm]     = useState({ symbol: "BTCUSDT", quantity: "" });
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const submit = async (side) => {
    if (!form.quantity || isNaN(form.quantity))
      return setStatus({ type: "err", msg: "Enter a valid quantity." });
    setLoading(true); setStatus(null);
    try {
      const { data } = await placeTrade(form.symbol, side, form.quantity);
      setStatus({
        type: "ok",
        msg: `✓ Order #${data.order_id} ${data.status} · ${data.executed_qty} @ avg $${fmt(data.avg_price)}`,
      });
      onTrade?.();
    } catch (err) {
      setStatus({ type: "err", msg: err.response?.data?.detail || "Trade failed" });
    } finally { setLoading(false); }
  };

  return (
    <div className="panel trade-panel">
      <h2 className="panel-title">EXECUTE TRADE</h2>
      <div className="trade-fields">
        <div className="field">
          <label>SYMBOL</label>
          <input value={form.symbol}
            onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
            placeholder="BTCUSDT" />
        </div>
        <div className="field">
          <label>QUANTITY</label>
          <input type="number" step="any" value={form.quantity}
            onChange={(e) => setForm({ ...form, quantity: e.target.value })}
            placeholder="0.001" />
        </div>
      </div>
      {status && (
        <p className={cls("trade-status", status.type === "err" ? "err-msg" : "ok-msg")}>
          {status.msg}
        </p>
      )}
      <div className="trade-btns">
        <button className="btn-buy"  onClick={() => submit("BUY")}  disabled={loading}>▲ BUY</button>
        <button className="btn-sell" onClick={() => submit("SELL")} disabled={loading}>▼ SELL</button>
      </div>
    </div>
  );
}

// ── Balance Table ─────────────────────────────────────────────────────────────
function BalanceTable({ balances, loading }) {
  if (loading)
    return <div className="panel"><p className="muted">Loading balances…</p></div>;
  if (!balances.length)
    return <div className="panel"><p className="muted">No non-zero balances found.</p></div>;
  return (
    <div className="panel">
      <h2 className="panel-title">PORTFOLIO HOLDINGS</h2>
      <table className="bal-table">
        <thead><tr><th>ASSET</th><th>AVAILABLE</th><th>LOCKED</th></tr></thead>
        <tbody>
          {balances.map((b) => (
            <tr key={b.asset}>
              <td><span className="asset-badge">{b.asset}</span></td>
              <td>{fmt(b.free)}</td>
              <td className="muted">{fmt(b.locked)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
function Dashboard({ onLogout }) {
  const [prices, setPrices]   = useState({});
  const [prevPrices, setPrev] = useState({});
  const [balances, setBalances] = useState([]);
  const [balLoading, setBal]  = useState(true);
  const prevRef = useRef({});

  const fetchPrices = async () => {
    try {
      const { data } = await getPrices("BTCUSDT,ETHUSDT");
      setPrev({ ...prevRef.current });
      const map = {};
      data.forEach((d) => (map[d.symbol] = d.price));
      prevRef.current = map;
      setPrices(map);
    } catch (_) {}
  };

  const fetchBalances = async () => {
    setBal(true);
    try { const { data } = await getBalance(); setBalances(data); }
    catch (_) { setBalances([]); }
    finally { setBal(false); }
  };

  useEffect(() => {
    fetchPrices(); fetchBalances();
    const id = setInterval(fetchPrices, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="dashboard">
      <header className="dash-header">
        <div className="dash-logo">
          ◈ PORTFOLIO TRACKER
          <span className="testnet-badge">TESTNET</span>
        </div>
        <button className="btn-logout" onClick={onLogout}>LOGOUT</button>
      </header>

      <section className="prices-row">
        {["BTCUSDT", "ETHUSDT"].map((s) => (
          <PriceCard key={s} symbol={s} price={prices[s] || "0"} prev={prevPrices[s]} />
        ))}
      </section>

      <section className="lower-grid">
        <TradePanel onTrade={fetchBalances} />
        <BalanceTable balances={balances} loading={balLoading} />
      </section>
    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [authed, setAuthed] = useState(!!localStorage.getItem("token"));
  const logout = () => { localStorage.removeItem("token"); setAuthed(false); };
  return (
    <>
      <style>{CSS}</style>
      {authed
        ? <Dashboard onLogout={logout} />
        : <LoginPage onLogin={() => setAuthed(true)} />}
    </>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:      #07080c;
    --surface: #0e1018;
    --border:  #1e2130;
    --accent:  #c8fb4a;
    --green:   #4afb8c;
    --red:     #fb4a6a;
    --muted:   #4a5068;
    --text:    #d4d8e8;
    --mono:    'Space Mono', monospace;
    --sans:    'DM Sans', sans-serif;
  }
  body { background: var(--bg); color: var(--text); font-family: var(--sans); min-height: 100vh; }

  /* Login */
  .login-root {
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
    background: radial-gradient(ellipse 80% 60% at 50% -10%, #1a2a0a 0%, var(--bg) 70%);
  }
  .login-card {
    width: 380px; padding: 48px 40px;
    background: var(--surface); border: 1px solid var(--border); border-top: 2px solid var(--accent);
  }
  .login-brand { text-align: center; margin-bottom: 36px; }
  .brand-hex { font-size: 2rem; color: var(--accent); }
  .login-brand h1 {
    font-family: var(--mono); font-size: 1.4rem; line-height: 1.2;
    letter-spacing: 0.12em; color: #fff; margin-top: 8px;
  }
  .brand-sub { font-size: 0.7rem; color: var(--muted); letter-spacing: 0.15em; margin-top: 6px; }
  .login-form { display: flex; flex-direction: column; gap: 16px; }
  .field { display: flex; flex-direction: column; gap: 6px; }
  label { font-family: var(--mono); font-size: 0.65rem; letter-spacing: 0.12em; color: var(--muted); }
  input {
    background: var(--bg); border: 1px solid var(--border); color: var(--text);
    font-family: var(--mono); font-size: 0.85rem; padding: 10px 12px;
    outline: none; transition: border-color 0.15s;
  }
  input:focus { border-color: var(--accent); }
  input::placeholder { color: var(--muted); }
  .btn-primary {
    margin-top: 8px; padding: 13px; background: var(--accent); color: #07080c;
    font-family: var(--mono); font-size: 0.75rem; font-weight: 700;
    letter-spacing: 0.1em; border: none; cursor: pointer; transition: opacity 0.15s;
  }
  .btn-primary:hover:not(:disabled) { opacity: 0.88; }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .err-msg { color: var(--red);   font-size: 0.75rem; font-family: var(--mono); }
  .ok-msg  { color: var(--green); font-size: 0.75rem; font-family: var(--mono); }
  .login-hint { text-align: center; font-size: 0.68rem; color: var(--muted); margin-top: 20px; font-family: var(--mono); }

  /* Dashboard */
  .dashboard { max-width: 1100px; margin: 0 auto; padding: 24px; }
  .dash-header {
    display: flex; justify-content: space-between; align-items: center;
    padding-bottom: 20px; border-bottom: 1px solid var(--border); margin-bottom: 28px;
  }
  .dash-logo { font-family: var(--mono); font-size: 0.9rem; letter-spacing: 0.1em; color: var(--accent); }
  .testnet-badge {
    margin-left: 10px; padding: 2px 8px; background: #1a2a0a; color: var(--accent);
    font-size: 0.6rem; border: 1px solid var(--accent); letter-spacing: 0.15em;
    vertical-align: middle; display: inline-block;
  }
  .btn-logout {
    font-family: var(--mono); font-size: 0.65rem; letter-spacing: 0.1em;
    color: var(--muted); background: none; border: 1px solid var(--border);
    padding: 7px 14px; cursor: pointer; transition: color 0.15s, border-color 0.15s;
  }
  .btn-logout:hover { color: var(--text); border-color: var(--text); }

  /* Prices */
  .prices-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
  .price-card {
    background: var(--surface); border: 1px solid var(--border);
    padding: 24px 28px; transition: border-top-color 0.4s;
  }
  .price-card.tick-up   { border-top: 2px solid var(--green); }
  .price-card.tick-down { border-top: 2px solid var(--red); }
  .price-symbol {
    display: block; font-family: var(--mono); font-size: 0.7rem;
    letter-spacing: 0.12em; color: var(--muted); margin-bottom: 10px;
  }
  .price-symbol span { color: #2e3348; }
  .price-val { display: block; font-family: var(--mono); font-size: 2rem; color: #fff; letter-spacing: -0.02em; }
  .price-delta { display: block; font-family: var(--mono); font-size: 0.7rem; margin-top: 8px; }
  .price-delta.green { color: var(--green); }
  .price-delta.red   { color: var(--red); }

  /* Lower grid */
  .lower-grid { display: grid; grid-template-columns: 1fr 1.5fr; gap: 16px; }
  .panel { background: var(--surface); border: 1px solid var(--border); padding: 28px; }
  .panel-title {
    font-family: var(--mono); font-size: 0.65rem; letter-spacing: 0.15em;
    color: var(--muted); margin-bottom: 22px; border-bottom: 1px solid var(--border); padding-bottom: 12px;
  }

  /* Trade */
  .trade-fields { display: flex; flex-direction: column; gap: 14px; }
  .trade-status { margin-top: 14px; font-size: 0.72rem; font-family: var(--mono); line-height: 1.4; }
  .trade-btns { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 20px; }
  .btn-buy, .btn-sell {
    padding: 12px; font-family: var(--mono); font-size: 0.75rem; font-weight: 700;
    letter-spacing: 0.08em; border: none; cursor: pointer; transition: opacity 0.15s;
  }
  .btn-buy  { background: var(--green); color: #07080c; }
  .btn-sell { background: var(--red);   color: #07080c; }
  .btn-buy:hover:not(:disabled), .btn-sell:hover:not(:disabled) { opacity: 0.85; }
  .btn-buy:disabled, .btn-sell:disabled { opacity: 0.45; cursor: not-allowed; }

  /* Balance */
  .bal-table { width: 100%; border-collapse: collapse; font-family: var(--mono); font-size: 0.78rem; }
  .bal-table th {
    text-align: left; color: var(--muted); font-size: 0.62rem; letter-spacing: 0.12em;
    padding-bottom: 12px; border-bottom: 1px solid var(--border);
  }
  .bal-table td { padding: 11px 0; border-bottom: 1px solid #12151e; }
  .asset-badge {
    display: inline-block; background: #0e1420; color: var(--accent);
    border: 1px solid #1a2a0a; padding: 2px 8px; font-size: 0.7rem; letter-spacing: 0.1em;
  }
  .muted { color: var(--muted); font-size: 0.8rem; font-family: var(--mono); }

  @media (max-width: 700px) {
    .prices-row, .lower-grid { grid-template-columns: 1fr; }
    .price-val { font-size: 1.5rem; }
  }
`;
