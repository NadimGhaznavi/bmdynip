import {ApiError, snapshot, addRecord, removeRecord} from './api.js';

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
  addButton.disabled = !ready || busy;
  input.disabled = !ready || mutating;
  for (const button of rows.querySelectorAll('button')) button.disabled = !ready || busy;
}

function time(node, value, fallback) {
  if (value) {
    node.dateTime = value;
    node.textContent = new Date(value).toLocaleString();
  } else {
    node.removeAttribute('datetime');
    node.textContent = fallback;
  }
}

function render(data) {
  current = data;
  const {records, messages} = data;
  for (const node of document.querySelectorAll('.domain-name')) node.textContent = data.domain;
  document.getElementById('domain-suffix').textContent = `.${data.domain}`;
  document.getElementById('public-ip').textContent = data.publicIp || 'Awaiting first check';
  time(document.getElementById('last-ip-check'), data.lastCheckedOn, 'Awaiting first check');
  time(document.getElementById('last-dns-update'), data.lastAppliedOn, 'Awaiting first update');
  document.getElementById('worker-error-row').hidden = !data.lastError;
  document.getElementById('worker-error').textContent = data.lastError || '';
  document.getElementById('hostname-count').textContent = `${records.length} hostname${records.length === 1 ? '' : 's'}`;
  connection.textContent = data.lastError ? 'Update failed' : 'Connected';
  connection.classList.toggle('badge-error', Boolean(data.lastError));
  connectionMessage.textContent = 'Live status refreshes every five seconds.';
  connectionMessage.classList.remove('error');
  rows.replaceChildren();
  for (const record of records) {
    const row = document.createElement('tr');
    cell(row, code(record.hostname));
    cell(row, 'A');
    cell(row, record.address ? code(record.address) : 'Awaiting update');
    const badge = document.createElement('span');
    badge.className = 'badge badge-idle';
    badge.textContent = record.status;
    cell(row, badge);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'danger';
    button.textContent = 'Delete';
    button.setAttribute('aria-label', `Delete ${record.hostname}`);
    button.addEventListener('click', () => {
      deleting = record;
      deleteTrigger = button;
      document.getElementById('delete-name').textContent = record.hostname;
      dialog.showModal();
    });
    cell(row, button).className = 'actions';
    rows.append(row);
  }
  if (!records.length) {
    const row = document.createElement('tr');
    const td = cell(row, 'No hostnames yet. Add a hostname above to get started.');
    td.colSpan = 5;
    td.className = 'empty-state';
    rows.append(row);
  }
  activity.replaceChildren();
  for (const entry of messages) {
    const row = document.createElement('tr');
    const time = document.createElement('time');
    time.dateTime = entry.timestamp;
    time.textContent = new Date(entry.timestamp).toLocaleString();
    cell(row, time);
    cell(row, entry.source);
    cell(row, entry.message);
    activity.append(row);
  }
  if (!messages.length) {
    const row = document.createElement('tr');
    const td = cell(row, 'No DNS change history yet.');
    td.colSpan = 3;
    td.className = 'empty-state';
    activity.append(row);
  }
}

async function loadSnapshot() {
  try {
    render(await snapshot());
    ready = true;
    return true;
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    ready = false;
    connection.textContent = 'Unavailable';
    connection.classList.add('badge-error');
    connectionMessage.textContent = `${error.message} ` +
      (current ? 'Displayed values may be out of date. Retrying…' : 'Retrying…');
    connectionMessage.classList.add('error');
    return false;
  }
}

async function refresh() {
  if (busy || deleting || dialog.open) return;
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
  if (busy || !ready) return;
  busy = mutating = true;
  controls();
  message('Saving…');
  try {
    await operation();
    afterSave();
    const refreshed = await loadSnapshot();
    message(success + (refreshed ? '' : ' Saved, but live status could not be refreshed. Retrying…'));
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
  await changeRecord(() => addRecord(name), `Added ${name}.${current.domain}. It will be updated on the next runner execution.`,
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
