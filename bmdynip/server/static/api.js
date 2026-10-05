export class ApiError extends Error {
  constructor(message, status = null) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  let result;
  try {
    response = await fetch(path, {cache: 'no-store', ...options,
      signal: AbortSignal.timeout(15000)});
    result = await response.json();
  } catch (error) {
    throw new ApiError(error.name === 'TimeoutError'
      ? 'The request timed out.' : 'Could not read a response from the server.');
  }
  if (!response.ok) throw new ApiError(result.error || 'The request failed.', response.status);
  return result;
}

export function snapshot() {
  return request('/api/snapshot');
}

export function dnsStatus(identity) {
  return request(`/api/records/${identity}/dns`);
}

export function addRecord(name) {
  return request('/api/records', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})});
}

export function removeRecord(identity) {
  return request(`/api/records/${identity}`, {method: 'DELETE',
    headers: {'Content-Type': 'application/json'}});
}
