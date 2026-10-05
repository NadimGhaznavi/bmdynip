const frame = document.getElementById('control');
const report = document.getElementById('result');
const checks = [];
const wait = async (predicate, description) => {
  for (let attempt = 0; attempt < 300; attempt++) {
    if (predicate()) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(`Timed out: ${description}`);
};
const assert = (condition, description) => {
  if (!condition) throw new Error(description);
  checks.push(description);
};
const doc = () => frame.contentDocument;
const node = selector => doc().querySelector(selector);
const ready = () => node('#hostname') && !node('#hostname').disabled &&
  !node('#add-hostname button').disabled;
const contains = hostname => node('#hostname-rows').textContent.includes(hostname);
const add = async name => {
  await wait(ready, 'hostname controls available');
  node('#hostname').value = name;
  node('#add-hostname').requestSubmit();
};
const outage = async failed => {
  await fetch('/__failure', {method: 'POST', body: JSON.stringify({failed})});
};

try {
  await wait(ready, 'initial live snapshot');
  await wait(() => !node('#hostname-rows').textContent.includes('Checking DNS'), 'initial DNS lookups');
  assert(node('#domain-suffix').textContent === '.example.test', 'Configured domain is displayed');
  assert(node('#public-ip').textContent === '8.8.8.8', 'Observed public IP is displayed');
  assert(node('#last-ip-check').dateTime && node('#last-dns-update').dateTime, 'Check and update times are displayed');
  assert(contains('existing.example.test') && node('#hostname-rows').textContent.includes('Current'), 'Applied record is current');
  assert(contains('failed.example.test') && node('#hostname-rows').textContent.includes('Not found'), 'Missing DNS record is shown');
  assert(!node('#worker-error-row').hidden && node('#worker-error').textContent.includes('Provider unavailable'), 'Last worker error is displayed');
  assert(!node('#worker-error img') && !node('#activity-rows img') && !frame.contentWindow.injected, 'Error text is rendered as text');
  const view = frame.contentWindow;
  const pollingFetch = view.fetch.bind(view);
  const existingRow = node('#hostname-rows').firstElementChild;
  const existingButton = existingRow.querySelector('button');
  const existingBadge = existingRow.querySelector('[data-dns-id]');
  const historyRow = node('#activity-rows').firstElementChild;
  const historyText = historyRow.cells[2].firstChild;
  const mutations = [];
  const observer = new view.MutationObserver(changes => mutations.push(...changes));
  for (const target of [node('#hostname-rows'), node('#activity-rows'), node('#add-hostname'),
    node('#public-ip'), node('#last-ip-check'), node('#connection-status')]) {
    observer.observe(target, {subtree: true, childList: true, characterData: true, attributes: true});
  }
  existingButton.focus();
  node('#hostname').value = 'unsaved';
  let polls = 0;
  view.fetch = async (path, options) => {
    const response = await pollingFetch(path, options);
    if (path === '/api/snapshot') polls++;
    return response;
  };
  await wait(() => polls >= 2, 'two unchanged background polls');
  await new Promise(resolve => setTimeout(resolve, 100));
  assert(mutations.length === 0, 'Unchanged polling makes no table, summary, or control DOM changes');
  assert(doc().activeElement === existingButton && node('#hostname').value === 'unsaved',
    'Polling preserves keyboard focus and unsaved input');
  view.fetch = async (path, options) => {
    const response = await pollingFetch(path, options);
    if (path === '/api/snapshot') {
      const values = await response.json();
      values.messages[0].message = 'Changed status message';
      return new view.Response(JSON.stringify(values), {status: 200});
    }
    if (path === `/api/records/${existingBadge.dataset.dnsId}/dns`) {
      const values = await response.json();
      values.status = 'Mismatch';
      return new view.Response(JSON.stringify(values), {status: 200});
    }
    return response;
  };
  await wait(() => existingBadge.textContent === 'Mismatch' && historyText.data === 'Changed status message',
    'changed message and DNS status');
  assert(node('#hostname-rows').firstElementChild === existingRow &&
    node('#activity-rows').firstElementChild === historyRow && historyRow.cells[2].firstChild === historyText,
    'Changed status text retains existing rows and text nodes');
  assert(!mutations.some(change => change.type === 'childList'), 'Status changes update text without rebuilding table content');
  observer.disconnect();
  view.fetch = pollingFetch;
  await wait(() => historyText.data !== 'Changed status message', 'original status restored');
  const history = [...node('#activity-rows').children].map(row => row.textContent);
  const initialCount = node('#hostname-rows').children.length;
  await add(' NewHost ');
  await wait(() => contains('newhost.example.test') && ready(), 'new hostname saved');
  assert(node('#hostname-feedback').textContent.startsWith('Added newhost.example.test.'), 'Add reports a committed save');
  assert(node('#hostname-feedback').textContent.includes('Runner started.'), 'Add reports immediate runner launch');
  assert(node('#activity-rows').textContent.includes('Added newhost.example.test; starting the runner.'),
    'Hostname addition appears in status messages');
  assert(node('#activity-rows').textContent.includes('bmdynip.server.__main__'), 'Status source is a module name');
  await add('newhost');
  await wait(() => node('#hostname-feedback').textContent.includes('already exists') && ready(), 'duplicate rejected');
  assert(node('#hostname-rows').children.length === initialCount + 1, 'Duplicate does not create another row');
  await add('bad.name');
  await wait(() => node('#hostname').getAttribute('aria-invalid') === 'true' && ready(), 'invalid name rejected');
  assert(node('#hostname-rows').children.length === initialCount + 1, 'Invalid input does not change records');
  const previousDocument = doc();
  frame.contentWindow.location.reload();
  await wait(() => doc() !== previousDocument && ready(), 'page reloaded');
  assert(contains('newhost.example.test'), 'Hostname survives reload');
  const deleteButton = () => [...node('#hostname-rows').querySelectorAll('tr')]
    .find(row => row.textContent.includes('newhost.example.test')).querySelector('button');
  deleteButton().click();
  await wait(() => node('#delete-dialog').open, 'delete confirmation');
  await new Promise(resolve => setTimeout(resolve, 5500));
  node('#delete-dialog button[value="cancel"]').click();
  await wait(() => !node('#delete-dialog').open, 'delete cancelled');
  await wait(() => doc().activeElement === deleteButton(), 'cancel focus restored');
  assert(contains('newhost.example.test'), 'Cancel retains the hostname');
  assert(doc().activeElement === deleteButton(), 'Cancel restores focus after a polling interval');
  deleteButton().click();
  node('#confirm-delete').click();
  await wait(() => !contains('newhost.example.test') && ready(), 'delete saved');
  assert(node('#hostname-feedback').textContent.includes('GoDaddy record was retained'), 'Delete explains retained DNS record');
  assert(history.every(entry => [...node('#activity-rows').children].some(row => row.textContent === entry)),
    'Existing change history is retained');

  const win = frame.contentWindow;
  const originalFetch = win.fetch.bind(win);
  let writes = 0;
  win.fetch = async (path, options) => {
    const response = await originalFetch(path, options);
    if (path === '/api/records' && options?.method === 'POST') {
      writes++;
      throw new win.DOMException('test-only lost response', 'TimeoutError');
    }
    return response;
  };
  await add('uncertain');
  await wait(() => contains('uncertain.example.test') && ready(), 'lost response reconciled');
  assert(node('#hostname-feedback').textContent.includes('before retrying'), 'Lost response does not report a confirmed save');
  assert(writes === 1, 'Uncertain writes are not automatically retried');
  win.fetch = async (path, options) => {
    const response = await originalFetch(path, options);
    if (path === '/api/records' && options?.method === 'POST') await outage(true);
    return response;
  };
  await add('saved');
  await wait(() => node('#connection-status').textContent === 'Unavailable', 'post-save refresh failure');
  assert(node('#hostname-feedback').textContent.includes('Saved, but live status could not be refreshed'), 'Committed save is distinguished from refresh failure');
  assert(node('#hostname').disabled, 'Unavailable status disables edits');
  assert([...node('#hostname-rows').querySelectorAll('button')].every(button => button.disabled), 'Unavailable status disables deletes');
  win.fetch = originalFetch;
  await outage(false);
  await wait(ready, 'database recovery');
  assert(contains('saved.example.test'), 'Committed hostname appears after recovery');
  await fetch('/__runner-failure', {method: 'POST'});
  await add('launch-failed');
  await wait(() => contains('launch-failed.example.test') && ready(), 'hostname retained after launch failure');
  assert(node('#hostname-feedback').textContent.includes('The runner could not start'), 'Launch failure reports a saved hostname');
  assert(node('#hostname-feedback').classList.contains('error'), 'Launch failure is displayed as an error');
  report.dataset.result = 'passed';
  report.textContent = `PASS: ${checks.length} browser checks\n${checks.join('\n')}`;
} catch (error) {
  report.dataset.result = 'failed';
  report.textContent = `FAIL: ${error.message}\n${checks.join('\n')}`;
}
