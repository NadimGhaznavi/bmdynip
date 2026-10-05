import {ApiError, snapshot, dnsStatus, addRecord, removeRecord} from './api.js';

const form = document.getElementById('add-hostname');
const input = document.getElementById('hostname');
const addButton = form.querySelector('button');
const feedback = document.getElementById('hostname-feedback');
const rows = document.getElementById('hostname-rows');
const activity = document.getElementById('activity-rows');
const dialog = document.getElementById('delete-dialog');
const connection = document.getElementById('connection-status');
const connectionMessage = document.getElementById('connection-message');
let deleting = null;
let deleteTrigger = null;
let current = null;
let ready = false;
let busy = false;
let mutating = false;
const dnsResults = new Map();
const dnsPending = new Set();
const hostnameRows = new Map();
const messageRows = new Map();
let snapshotRequest = 0;

function text(node, value) {
  if (node.textContent === value) return;
  if (node.childNodes.length === 1 && node.firstChild.nodeType === Node.TEXT_NODE) {
    node.firstChild.data = value;
  } else {
    node.textContent = value;
  }
}

function attribute(node, name, value) {
  if (node.getAttribute(name) !== value) node.setAttribute(name, value);
}

function toggleClass(node, name, enabled) {
  if (node.classList.contains(name) !== enabled) node.classList.toggle(name, enabled);
}

function placeRows(container, desired) {
  const keep = new Set(desired);
  for (const row of [...container.children]) if (!keep.has(row)) row.remove();
  desired.forEach((row, index) => {
    if (container.children[index] !== row) container.insertBefore(row, container.children[index] || null);
  });
}

function emptyRow(value, columns) {
  const row = document.createElement('tr');
  const td = cell(row, value);
  td.colSpan = columns;
  td.className = 'empty-state';
  return row;
}

const noHostnames = emptyRow('No hostnames yet. Add a hostname above to get started.', 5);
const noMessages = emptyRow('No DNS change history yet.', 3);

function dnsBadge(badge, result) {
  text(badge, result?.status || 'Checking DNS…');
  attribute(badge, 'title', result?.dnsAddresses?.length ? `DNS: ${result.dnsAddresses.join(', ')}` : '');
}

function checkDns(data) {
  for (const record of data.records) {
    if (dnsPending.has(record.id)) continue;
    dnsPending.add(record.id);
    const expectedAddress = data.publicIp || record.address;
    dnsStatus(record.id).catch(error => {
      if (!(error instanceof ApiError)) throw error;
      return {status: 'Lookup failed', dnsAddresses: [], expectedAddress};
    }).then(result => {
      const present = current?.records.find(row => row.id === record.id);
      if (!present || result.expectedAddress !== (current.publicIp || present.address)) return;
      dnsResults.set(record.id, result);
      const badge = rows.querySelector(`[data-dns-id="${record.id}"]`);
      if (badge) dnsBadge(badge, result);
    }).finally(() => dnsPending.delete(record.id));
  }
  for (const identity of dnsResults.keys()) {
    if (!data.records.some(record => record.id === identity)) dnsResults.delete(identity);
  }
}

function cell(row, value) {
  const td = document.createElement('td');
  if (typeof value === 'string') td.textContent = value;
  else td.append(value);
  row.append(td);
  return td;
}

function code(value) {
  const node = document.createElement('code');
  node.textContent = value;
  return node;
}

function message(value, error = false, invalid = false) {
  feedback.textContent = value;
  feedback.classList.toggle('error', error);
  input.setAttribute('aria-invalid', String(invalid));
}

function controls() {
  for (const control of [addButton, input, ...rows.querySelectorAll('button')]) {
    const disabled = !ready || mutating;
    if (control.disabled !== disabled) control.disabled = disabled;
  }
}

function time(node, value, fallback) {
  if (value) {
    attribute(node, 'datetime', value);
    text(node, new Date(value).toLocaleString());
  } else {
    if (node.hasAttribute('datetime')) node.removeAttribute('datetime');
    text(node, fallback);
  }
}

function render(data) {
  current = data;
  const {records, messages} = data;
  for (const node of document.querySelectorAll('.domain-name')) text(node, data.domain);
  text(document.getElementById('domain-suffix'), `.${data.domain}`);
  text(document.getElementById('public-ip'), data.publicIp || 'Awaiting first check');
  time(document.getElementById('last-ip-check'), data.lastCheckedOn, 'Awaiting first check');
  time(document.getElementById('last-dns-update'), data.lastSubmittedOn || data.lastAppliedOn,
    'Awaiting first submission');
  const errorRow = document.getElementById('worker-error-row');
  if (errorRow.hidden !== !data.lastError) errorRow.hidden = !data.lastError;
  text(document.getElementById('worker-error'), data.lastError || '');
  text(document.getElementById('hostname-count'), `${records.length} hostname${records.length === 1 ? '' : 's'}`);
  text(connection, data.lastError ? 'Update failed' : 'Connected');
  toggleClass(connection, 'badge-error', Boolean(data.lastError));
  text(connectionMessage, 'Live status refreshes every five seconds.');
  toggleClass(connectionMessage, 'error', false);
  const desiredHostnames = [];
  for (const record of records) {
    let row = hostnameRows.get(record.id);
    if (!row) {
      row = document.createElement('tr');
      cell(row, code(record.hostname));
      cell(row, 'A');
      cell(row, record.address ? code(record.address) : 'Awaiting update');
      row.dataset.address = record.address || '';
      const badge = document.createElement('span');
      badge.className = 'badge badge-idle';
      badge.dataset.dnsId = record.id;
      cell(row, badge);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'danger';
      button.textContent = 'Delete';
      button.addEventListener('click', () => {
        deleting = current.records.find(value => value.id === record.id);
        if (!deleting) return;
        deleteTrigger = button;
        text(document.getElementById('delete-name'), deleting.hostname);
        dialog.showModal();
      });
      cell(row, button).className = 'actions';
      hostnameRows.set(record.id, row);
    }
    text(row.cells[0].firstChild, record.hostname);
    if (row.dataset.address !== (record.address || '')) {
      if (record.address && row.cells[2].firstChild.nodeName === 'CODE') {
        text(row.cells[2].firstChild, record.address);
      } else {
        row.cells[2].replaceChildren(record.address ? code(record.address) : 'Awaiting update');
      }
      row.dataset.address = record.address || '';
    }
    const dns = dnsResults.get(record.id);
    dnsBadge(row.cells[3].firstChild,
      dns?.expectedAddress === (data.publicIp || record.address) ? dns : null);
    attribute(row.cells[4].firstChild, 'aria-label', `Delete ${record.hostname}`);
    desiredHostnames.push(row);
  }
  const identities = new Set(records.map(record => record.id));
  for (const identity of hostnameRows.keys()) if (!identities.has(identity)) hostnameRows.delete(identity);
  placeRows(rows, desiredHostnames.length ? desiredHostnames : [noHostnames]);

  const desiredMessages = [];
  const occurrences = new Map();
  const messageKeys = new Set();
  for (const entry of messages) {
    const base = JSON.stringify([entry.timestamp, entry.source]);
    const occurrence = occurrences.get(base) || 0;
    occurrences.set(base, occurrence + 1);
    const key = JSON.stringify([entry.timestamp, entry.source, occurrence]);
    messageKeys.add(key);
    let row = messageRows.get(key);
    if (!row) {
      row = document.createElement('tr');
      cell(row, document.createElement('time'));
      cell(row, entry.source);
      cell(row, entry.message);
      messageRows.set(key, row);
    }
    time(row.cells[0].firstChild, entry.timestamp, '');
    text(row.cells[1], entry.source);
    text(row.cells[2], entry.message);
    desiredMessages.push(row);
  }
  for (const key of messageRows.keys()) if (!messageKeys.has(key)) messageRows.delete(key);
  placeRows(activity, desiredMessages.length ? desiredMessages : [noMessages]);
}

async function loadSnapshot() {
  const request = ++snapshotRequest;
  try {
    const data = await snapshot();
    if (request !== snapshotRequest) return false;
    render(data);
    checkDns(data);
    ready = true;
    return true;
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    if (request !== snapshotRequest) return false;
    ready = false;
    text(connection, 'Unavailable');
    toggleClass(connection, 'badge-error', true);
    text(connectionMessage, `${error.message} ` +
      (current ? 'Displayed values may be out of date. Retrying…' : 'Retrying…'));
    toggleClass(connectionMessage, 'error', true);
    return false;
  }
}

async function refresh() {
  if (busy || mutating || deleting || dialog.open) return;
  busy = true;
  controls();
  try {
    await loadSnapshot();
  } finally {
    busy = false;
    controls();
  }
}

async function changeRecord(operation, success, afterSave = () => {}) {
  if (mutating || !ready) return;
  snapshotRequest++;
  busy = mutating = true;
  controls();
  message('Saving…');
  try {
    const result = await operation();
    afterSave();
    const refreshed = await loadSnapshot();
    const outcome = typeof success === 'function' ? success(result) : success;
    message(outcome + (refreshed ? '' : ' Saved, but live status could not be refreshed. Retrying…'),
      result.runnerStarted === false);
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    message(error.status === null
      ? `${error.message} Check the hostname list after it refreshes before retrying.`
      : error.message, true, error.status === 400);
    await loadSnapshot();
  } finally {
    busy = mutating = false;
    controls();
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const name = input.value.trim().toLowerCase();
  if (!current) return;
  await changeRecord(() => addRecord(name), result => `Added ${name}.${current.domain}. ` +
    (result.runnerStarted ? 'Runner started. DNS status will refresh automatically.' :
      'The runner could not start. Check the service log; the hostname is saved for the next scheduled or manual run.'),
    () => { input.value = ''; });
  input.focus();
});

input.addEventListener('input', () => {
  input.removeAttribute('aria-invalid');
  feedback.classList.remove('error');
  feedback.textContent = '';
});

dialog.addEventListener('close', async () => {
  const record = deleting;
  const confirmed = dialog.returnValue === 'delete';
  deleting = null;
  dialog.returnValue = '';
  if (confirmed && record) {
    await changeRecord(() => removeRecord(record.id), `Stopped managing ${record.hostname}. Its GoDaddy record was retained.`);
    input.focus();
  } else {
    deleteTrigger?.focus();
  }
});

refresh();
setInterval(refresh, 5000);
