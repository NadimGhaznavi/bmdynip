"use strict";

const scheduleForm = document.getElementById('schedule-form');
const scheduleEnabled = document.getElementById('schedule-enabled');
const scheduleExpression = document.getElementById('schedule-expression');
const scheduleStatus = document.getElementById('schedule-status');
const scheduleButton = scheduleForm.querySelector('button');

function scheduleBusy(busy) {
  scheduleButton.disabled = scheduleEnabled.disabled = scheduleExpression.disabled = busy;
}

function showSchedule(values, saved = false) {
  scheduleEnabled.checked = values.enabled;
  scheduleExpression.value = values.expression;
  scheduleStatus.textContent = (saved ? 'Schedule saved. ' : '') +
    (values.enabled ? 'Scheduled runner enabled.' : 'Scheduled runner disabled.');
  scheduleStatus.classList.remove('error');
}

async function requestSchedule(options = {}) {
  const response = await fetch('/api/runner-schedule', {
    ...options, signal: AbortSignal.timeout(15000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Could not read the runner schedule.');
  return result.schedule;
}

scheduleForm.addEventListener('submit', async event => {
  event.preventDefault();
  const values = {enabled: scheduleEnabled.checked, expression: scheduleExpression.value};
  scheduleBusy(true);
  scheduleStatus.textContent = 'Saving schedule…';
  try {
    showSchedule(await requestSchedule({method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values)}), true);
  } catch (error) {
    scheduleStatus.textContent = error.name === 'TimeoutError'
      ? 'The save request timed out. Reload to check the saved schedule before retrying.'
      : error.message || 'Could not save the schedule.';
    scheduleStatus.classList.add('error');
  } finally {
    scheduleBusy(false);
  }
});

requestSchedule().then(values => {
  showSchedule(values);
  scheduleBusy(false);
}).catch(error => {
  scheduleStatus.textContent = `${error.message || 'Could not read the runner schedule.'} Reload to retry.`;
  scheduleStatus.classList.add('error');
});
