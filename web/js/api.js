// Bridge to the Python backend.
// In the app window: window.pywebview.api.<method>(...)  (pywebview)
// In a browser:      POST /api/<method>  (studio/devserver.py)

function waitForPywebview(ms = 400) {
  return new Promise((resolve) => {
    if (window.pywebview?.api) return resolve(true);
    const t0 = Date.now();
    window.addEventListener("pywebviewready", () => resolve(true), { once: true });
    const iv = setInterval(() => {
      if (window.pywebview?.api) { clearInterval(iv); resolve(true); }
      else if (Date.now() - t0 > ms && !window.pywebview) { clearInterval(iv); resolve(false); }
    }, 50);
  });
}

let native = null;

async function call(method, ...args) {
  if (native === null) native = await waitForPywebview();
  if (native) {
    try {
      return await window.pywebview.api[method](...args);
    } catch (e) {
      throw new Error(e?.message || String(e));
    }
  }
  const res = await fetch(`/api/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ args }),
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data.result;
}

// api.anything(...) -> call("anything", ...)
export const api = new Proxy({}, { get: (_, name) => (...args) => call(name, ...args) });
