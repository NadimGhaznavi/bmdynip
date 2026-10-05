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
  assert(node('#domain-suffix').textContent === '.example.test', 'Configured domain is displayed');
  assert(node('#public-ip').textContent === '8.8.8.8', 'Observed public IP is displayed');
  assert(node('#last-ip-check').dateTime && node('#last-dns-update').dateTime, 'Check and update times are displayed');
  assert(contains('existing.example.test') && node('#hostname-rows').textContent.includes('Current'), 'Applied record is current');
  assert(contains('failed.example.test') && node('#hostname-rows').textContent.includes('Pending'), 'Unapplied record is pending');
  assert(!node('#worker-error-row').hidden && node('#worker-error').textContent.includes('Provider unavailable'), 'Last worker error is displayed');
  assert(!node('#worker-error img') && !node('#activity-rows img') && !frame.contentWindow.injected, 'Error text is rendered as text');
  const history = node('#activity-rows').textContent;
  const initialCount = node('#hostname-rows').children.length;
  await add(' NewHost ');
  await wait(() => contains('newhost.example.test') && ready(), 'new hostname saved');
  assert(node('#hostname-feedback').textContent.startsWith('Added newhost.example.test.'), 'Add reports a committed save');
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
  assert(node('#activity-rows').textContent === history, 'Existing change history is retained');

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
  report.dataset.result = 'passed';
  report.textContent = `PASS: ${checks.length} browser checks\n${checks.join('\n')}`;
} catch (error) {
  report.dataset.result = 'failed';
  report.textContent = `FAIL: ${error.message}\n${checks.join('\n')}`;
}
