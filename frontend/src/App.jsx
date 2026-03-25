import { useEffect, useState } from "react";

const initialForm = {
  symbol: "BTCUSDT",
  side: "BUY",
  orderType: "MARKET",
  quantity: "0.001",
  price: "",
  stopPrice: "",
};

export default function App() {
  const [form, setForm] = useState(initialForm);
  const [credentialsForm, setCredentialsForm] = useState({
    apiKey: "",
    apiSecret: "",
  });
  const [credentials, setCredentials] = useState({
    loading: false,
    error: "",
    success: "",
  });
  const [health, setHealth] = useState({
    loading: true,
    error: "",
    data: null,
  });
  const [submission, setSubmission] = useState({
    loading: false,
    error: "",
    data: null,
  });

  const isLimitOrder = form.orderType === "LIMIT";
  const isStopMarketOrder = form.orderType === "STOP_MARKET";

  useEffect(() => {
    void loadHealth();
  }, []);

  async function loadHealth() {
    setHealth({ loading: true, error: "", data: null });

    try {
      const response = await fetch("/api/health");
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Unable to reach the Python API.");
      }

      setHealth({ loading: false, error: "", data });
    } catch (error) {
      setHealth({
        loading: false,
        error: error instanceof Error ? error.message : "Unable to reach the Python API.",
        data: null,
      });
    }
  }

  async function handleCredentialsSubmit(event) {
    event.preventDefault();
    setCredentials({ loading: true, error: "", success: "" });

    try {
      const response = await fetch("/api/session/credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: credentialsForm.apiKey,
          api_secret: credentialsForm.apiSecret,
        }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Unable to save credentials.");
      }

      setCredentials({
        loading: false,
        error: "",
        success: "Credentials saved for this backend session.",
      });
      setCredentialsForm({ apiKey: "", apiSecret: "" });
      void loadHealth();
    } catch (error) {
      setCredentials({
        loading: false,
        error: error instanceof Error ? error.message : "Unable to save credentials.",
        success: "",
      });
    }
  }

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
      ...(name === "orderType" && value === "MARKET" ? { price: "", stopPrice: "" } : {}),
      ...(name === "orderType" && value === "LIMIT" ? { stopPrice: "" } : {}),
      ...(name === "orderType" && value === "STOP_MARKET" ? { price: "" } : {}),
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmission({ loading: true, error: "", data: null });

    const payload = {
      symbol: form.symbol,
      side: form.side,
      order_type: form.orderType,
      quantity: form.quantity,
      ...(isLimitOrder ? { price: form.price } : {}),
      ...(isStopMarketOrder ? { stop_price: form.stopPrice } : {}),
    };

    try {
      const response = await fetch("/api/orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Order request failed.");
      }

      setSubmission({ loading: false, error: "", data });
      void loadHealth();
    } catch (error) {
      setSubmission({
        loading: false,
        error: error instanceof Error ? error.message : "Order request failed.",
        data: null,
      });
    }
  }

  const response = submission.data?.response;
  const credentialsConfigured = Boolean(health.data?.credentialsConfigured);

  return (
    <main className="shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <section className="hero panel">
        <div>
          <p className="eyebrow">Binance Futures Testnet</p>
          <h1>Trading Bot Control Room</h1>
          <p className="hero-copy">
            Launch market, limit, and stop-market orders from a React dashboard while the Python
            backend handles validation, signing, logging, and Binance API calls.
          </p>
        </div>

        <div className="hero-meta">
          <div className="status-chip">
            <span className={`dot ${health.error ? "dot-error" : "dot-ok"}`} />
            {health.loading ? "Checking backend" : health.error ? "Backend unavailable" : "Backend online"}
          </div>
          <button className="ghost-button" type="button" onClick={() => void loadHealth()}>
            Refresh status
          </button>
        </div>
      </section>

      <section className="grid">
        <article className="panel form-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Order Ticket</p>
              <h2>Place a testnet order</h2>
            </div>
            <span className={`pill ${form.orderType === "LIMIT" ? "pill-warm" : "pill-cool"}`}>
              {form.orderType}
            </span>
          </div>

          {!credentialsConfigured ? (
            <>
              <div className="message error-message">
                Binance credentials are missing on the backend. Add your testnet API key/secret below (stored in
                memory only).
              </div>
              <form className="order-form" onSubmit={handleCredentialsSubmit}>
                <label className="wide">
                  API Key
                  <input
                    name="apiKey"
                    value={credentialsForm.apiKey}
                    onChange={(e) =>
                      setCredentialsForm((current) => ({ ...current, apiKey: e.target.value }))
                    }
                    placeholder="Binance Futures Testnet API Key"
                    autoComplete="off"
                  />
                </label>
                <label className="wide">
                  API Secret
                  <input
                    name="apiSecret"
                    value={credentialsForm.apiSecret}
                    onChange={(e) =>
                      setCredentialsForm((current) => ({ ...current, apiSecret: e.target.value }))
                    }
                    placeholder="Binance Futures Testnet API Secret"
                    autoComplete="off"
                  />
                </label>
                <button className="submit-button" type="submit" disabled={credentials.loading}>
                  {credentials.loading ? "Saving..." : "Save credentials"}
                </button>
              </form>
              {credentials.error ? <div className="message error-message">{credentials.error}</div> : null}
              {credentials.success ? (
                <div className="message empty-state">{credentials.success}</div>
              ) : null}
            </>
          ) : (
            <>
              <form className="order-form" onSubmit={handleSubmit}>
                <label>
                  Symbol
                  <input name="symbol" value={form.symbol} onChange={handleChange} placeholder="BTCUSDT" />
                </label>

            <label>
              Side
              <select name="side" value={form.side} onChange={handleChange}>
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </label>

            <label>
              Order Type
              <select name="orderType" value={form.orderType} onChange={handleChange}>
                <option value="MARKET">MARKET</option>
                <option value="LIMIT">LIMIT</option>
                <option value="STOP_MARKET">STOP_MARKET</option>
              </select>
            </label>

            <label>
              Quantity
              <input
                name="quantity"
                value={form.quantity}
                onChange={handleChange}
                placeholder="0.001"
              />
            </label>

            <label className={isLimitOrder ? "price-visible" : "price-hidden"}>
              Limit Price
              <input
                name="price"
                value={form.price}
                onChange={handleChange}
                placeholder="80000"
                disabled={!isLimitOrder}
              />
            </label>

            <label className={isStopMarketOrder ? "price-visible" : "price-hidden"}>
              Stop Price
              <input
                name="stopPrice"
                value={form.stopPrice}
                onChange={handleChange}
                placeholder="78000"
                disabled={!isStopMarketOrder}
              />
            </label>

                <button className="submit-button" type="submit" disabled={submission.loading}>
                  {submission.loading ? "Submitting order..." : "Send to Binance Testnet"}
                </button>
              </form>

              {submission.error ? (
                <div className="message error-message">{submission.error}</div>
              ) : null}
            </>
          )}
        </article>

        <article className="panel status-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Backend Status</p>
              <h2>Connection snapshot</h2>
            </div>
          </div>

          {health.error ? (
            <div className="message error-message">{health.error}</div>
          ) : (
            <div className="metric-stack">
              <div className="metric-card">
                <span>API status</span>
                <strong>{health.loading ? "Loading..." : health.data?.status || "Unknown"}</strong>
              </div>
              <div className="metric-card">
                <span>Credentials</span>
                <strong>
                  {health.loading
                    ? "Checking..."
                    : health.data?.credentialsConfigured
                      ? "Configured"
                      : "Missing"}
                </strong>
              </div>
              <div className="metric-card wide">
                <span>Base URL</span>
                <strong className="mono">{health.data?.baseUrl || "Unavailable"}</strong>
              </div>
              <div className="metric-card wide">
                <span>Active log file</span>
                <strong className="mono">{health.data?.logFile || "Created on backend startup"}</strong>
              </div>
            </div>
          )}
        </article>
      </section>

      <section className="grid lower-grid">
        <article className="panel preview-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Request Preview</p>
              <h2>What will be sent</h2>
            </div>
          </div>

          <dl className="summary-list">
            <div>
              <dt>Symbol</dt>
              <dd>{form.symbol || "BTCUSDT"}</dd>
            </div>
            <div>
              <dt>Side</dt>
              <dd>{form.side}</dd>
            </div>
            <div>
              <dt>Type</dt>
              <dd>{form.orderType}</dd>
            </div>
            <div>
              <dt>Quantity</dt>
              <dd>{form.quantity || "0.001"}</dd>
            </div>
            <div>
              <dt>Price</dt>
              <dd>{isLimitOrder ? form.price || "Required" : "Not used"}</dd>
            </div>
            <div>
              <dt>Stop Price</dt>
              <dd>{isStopMarketOrder ? form.stopPrice || "Required" : "Not used"}</dd>
            </div>
          </dl>
        </article>

        <article className="panel response-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Exchange Response</p>
              <h2>Latest order result</h2>
            </div>
          </div>

          {submission.data ? (
            <div className="response-grid">
              <div className="response-card">
                <span>Message</span>
                <strong>{submission.data.message}</strong>
              </div>
              <div className="response-card">
                <span>orderId</span>
                <strong className="mono">{response?.orderId ?? "N/A"}</strong>
              </div>
              <div className="response-card">
                <span>Status</span>
                <strong>{response?.status ?? "N/A"}</strong>
              </div>
              <div className="response-card">
                <span>Executed Qty</span>
                <strong className="mono">{response?.executedQty ?? "N/A"}</strong>
              </div>
              <div className="response-card">
                <span>Avg Price</span>
                <strong className="mono">{response?.avgPrice ?? "N/A"}</strong>
              </div>
              <div className="response-card wide">
                <span>Log File</span>
                <strong className="mono">{submission.data.logFile}</strong>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              Submit an order and the latest Binance response will show up here.
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
