// api.js — TaskFlow API fetch helpers
const BASE = '';

async function _request(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(BASE + path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data;
}

export function get(path)        { return _request('GET',   path);       }
export function post(path, body) { return _request('POST',  path, body); }
export function patch(path, body){ return _request('PATCH', path, body); }
