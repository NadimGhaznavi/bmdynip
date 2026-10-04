import {demo} from './demo.js';

const form = document.getElementById('add-hostname');
const input = document.getElementById('hostname');
const feedback = document.getElementById('hostname-feedback');
const rows = document.getElementById('hostname-rows');
const activity = document.getElementById('activity-rows');
const dialog = document.getElementById('delete-dialog');
let deleting = null;
let deleteTrigger = null;

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

function message(value, error = false) {
  feedback.textContent = value;
  feedback.classList.toggle('error', error);
  input.setAttribute('aria-invalid', String(error));
}

function render() {
  const {records, messages} = demo.snapshot();
  document.getElementById('hostname-count').textContent = `${records.length} sample hostname${records.length === 1 ? '' : 's'}`;
  rows.replaceChildren();
  for (const record of records) {
    const row = document.createElement('tr');
    cell(row, code(record.hostname));
    cell(row, 'A');
    cell(row, code(record.address));
    const badge = document.createElement('span');
    badge.className = 'badge badge-idle';
    badge.textContent = 'Sample';
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
}

form.addEventListener('submit', event => {
  event.preventDefault();
  try {
    const name = demo.add(input.value);
    render();
    input.value = '';
    message(`Added ${name}.osoyalce.com to the preview.`);
  } catch (error) {
    message(error.message, true);
  }
  input.focus();
});

input.addEventListener('input', () => {
  input.removeAttribute('aria-invalid');
  feedback.classList.remove('error');
  feedback.textContent = '';
});

dialog.addEventListener('close', () => {
  if (dialog.returnValue === 'delete' && deleting) {
    try {
      demo.remove(deleting.name);
      render();
      message(`Deleted ${deleting.hostname} from the preview.`);
    } catch (error) {
      message(error.message, true);
    }
    input.focus();
  } else {
    deleteTrigger?.focus();
  }
  deleting = null;
  dialog.returnValue = '';
});

render();
