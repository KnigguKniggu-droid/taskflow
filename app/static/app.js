// app.js — Entry point; imports modules and wires events on DOMContentLoaded
import * as api from '/static/api.js';
import * as render from '/static/render.js';
import * as modal from '/static/modal.js';

let usersMap = new Map();   // id (number) → name (string)
let currentFilter = {};

async function loadUsers() {
  const data = await api.get('/users');
  usersMap = new Map(data.users.map(u => [u.id, u.name]));
  render.populateUserSelect(data.users, document.getElementById('filter-assignee'), '— All —');
  render.populateUserSelect(data.users, document.getElementById('ct-assignee'), 'Unassigned');
}

async function loadStats() {
  const data = await api.get('/tasks/stats');
  render.renderStatCards(data);
}

async function loadTasks(params) {
  const qs = buildQS(params);
  const taskList = document.getElementById('task-list');
  taskList.setAttribute('aria-busy', 'true');
  taskList.classList.add('is-loading');

  try {
    const data = await api.get('/tasks' + qs);
    taskList.innerHTML = '';
    taskList.classList.remove('is-loading');
    taskList.setAttribute('aria-busy', 'false');
    document.getElementById('task-list-error').hidden = true;

    if (data.tasks.length === 0) {
      const emptyEl = document.getElementById('task-list-empty');
      emptyEl.textContent = Object.keys(params).length === 0
        ? 'No tasks yet.'
        : 'No tasks found for this filter.';
      emptyEl.hidden = false;
    } else {
      document.getElementById('task-list-empty').hidden = true;
      for (const t of data.tasks) {
        const li = render.renderTask(t, usersMap);
        li.querySelector('.task-title-btn').addEventListener('click', e => {
          openTaskDetail(t.id, e.currentTarget);
        });
        taskList.appendChild(li);
      }
    }
  } catch (err) {
    taskList.classList.remove('is-loading');
    taskList.setAttribute('aria-busy', 'false');
    const errorEl = document.getElementById('task-list-error');
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  }
}

function buildQS(params) {
  const entries = Object.entries(params).filter(([, v]) => v !== '' && v != null && v !== false);
  if (entries.length === 0) return '';
  return '?' + new URLSearchParams(entries).toString();
}

async function openTaskDetail(taskId, returnEl) {
  // TODO M5
}

document.addEventListener('DOMContentLoaded', () => {
  // Filter form
  document.getElementById('filter-form').addEventListener('submit', e => {
    e.preventDefault();
    const assigneeId = document.getElementById('filter-assignee').value;
    const tag = document.getElementById('filter-tag').value.trim();
    currentFilter = {};
    if (assigneeId) currentFilter.assignee_id = assigneeId;
    if (tag) currentFilter.tag = tag;
    loadTasks(currentFilter).then(() => loadStats());
  });

  document.getElementById('btn-clear-filter').addEventListener('click', () => {
    document.getElementById('filter-form').reset();
    currentFilter = {};
    loadTasks({}).then(() => loadStats());
  });

  // Global error banner
  document.getElementById('btn-dismiss-error').addEventListener('click', () => {
    document.getElementById('error-banner').hidden = true;
  });

  // Initial load
  loadUsers().then(() => Promise.all([loadStats(), loadTasks({})]));
});

function showGlobalError(msg) {
  const banner = document.getElementById('error-banner');
  document.getElementById('error-banner-msg').textContent = msg;
  banner.hidden = false;
  setTimeout(() => { banner.hidden = true; }, 5000);
}
