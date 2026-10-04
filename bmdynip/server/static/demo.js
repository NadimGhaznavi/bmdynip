// Preview adapter: all state belongs to this page session.
// Replace this adapter when the HTTP API is available.
const domain = 'osoyalce.com';
const address = '203.0.113.42';
const names = new Set(['wintermute']);
const messages = [];

function log(message) {
  messages.unshift({timestamp: new Date().toISOString(), source: 'UI', message});
  messages.splice(100);
}

function validate(value) {
  const name = value.trim().toLowerCase();
  if (!/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(name)) {
    throw new Error('Enter one hostname label, up to 63 characters. Use letters, numbers, and hyphens; no dots.');
  }
  return name;
}

log('UI preview ready. DNS updates and the five-minute worker are not connected.');

export const demo = {
  snapshot() {
    return {
      records: [...names].sort().map(name => ({name, hostname: `${name}.${domain}`, address})),
      messages: messages.map(message => ({...message})),
    };
  },
  add(value) {
    const name = validate(value);
    if (names.has(name)) throw new Error(`${name}.${domain} is already in the hostname list.`);
    names.add(name);
    log(`Added ${name}.${domain} to the preview. No DNS changes made.`);
    return name;
  },
  remove(name) {
    if (!names.delete(name)) throw new Error('That hostname is no longer in the list.');
    log(`Deleted ${name}.${domain} from the preview. No DNS changes made.`);
  },
};
