// app.js — Entry point; imports modules and wires events on DOMContentLoaded
import * as api from '/static/api.js';
import * as render from '/static/render.js';
import * as modal from '/static/modal.js';

let usersMap = new Map();         // id (number) → name (string)
let currentFilter = {};
let currentDetailTaskId = null;   // id of the task currently shown in the detail dialog

async function loadUsers() {
  try {
    const data = await api.get('/users');
    usersMap = new Map(data.users.map(u => [u.id, u.name]));
    render.populateUserSelect(data.users, document.getElementById('filter-assignee'), '— All —');
    render.populateUserSelect(data.users, document.getElementById('ct-assignee'), 'Unassigned');
  } catch (err) {
    showGlobalError(err.message);
  }
}

async function loadStats() {
  try {
    const data = await api.get('/tasks/stats');
    render.renderStatCards(data);
  } catch (err) {
    showGlobalError(err.message);
  }
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

    // Update document.title to reflect active filter
    const assigneeId = params.assignee_id;
    const tag = params.tag;
    if (assigneeId && tag) {
      const name = usersMap.get(Number(assigneeId)) || assigneeId;
      document.title = `TaskFlow — assignee: ${name}, tag: ${tag}`;
    } else if (assigneeId) {
      const name = usersMap.get(Number(assigneeId)) || assigneeId;
      document.title = `TaskFlow — assignee: ${name}`;
    } else if (tag) {
      document.title = `TaskFlow — tag: ${tag}`;
    } else {
      document.title = 'TaskFlow';
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
  const detailDialog  = document.getElementById('modal-task-detail');
  const detailTitle   = document.getElementById('detail-title');
  const detailBody    = document.getElementById('detail-body');
  const detailError   = document.getElementById('detail-error');
  const editForm      = document.getElementById('detail-edit-form');
  const btnEditTask   = document.getElementById('btn-edit-task');

  // Reset to read view
  detailTitle.textContent = '…';
  detailBody.innerHTML    = '';
  detailError.hidden      = true;
  editForm.hidden         = true;
  detailBody.hidden       = false;
  btnEditTask.hidden      = true;

  modal.openModal(detailDialog, returnEl);

  try {
    const task = await api.get(`/tasks/${taskId}`);
    const { html, title } = render.renderTaskDetail(task, usersMap);
    detailTitle.textContent  = title;
    detailBody.innerHTML     = html;
    currentDetailTaskId      = task.id;
    btnEditTask.hidden        = false;
    render.renderEditForm(task, usersMap);

    // Wire "Mark Complete" button if present
    _wireCompleteButton(detailBody, taskId, detailDialog, detailError);
  } catch (err) {
    detailError.textContent = err.message;
    detailError.hidden = false;
  }
}

function _wireCompleteButton(detailBody, taskId, detailDialog, detailError) {
  const completeBtn = detailBody.querySelector('#btn-complete-task');
  if (!completeBtn) return;
  completeBtn.addEventListener('click', async () => {
    completeBtn.disabled = true;
    try {
      await api.post(`/tasks/${taskId}/complete`, {});
      modal.closeModal(detailDialog);
      await Promise.all([loadStats(), loadTasks(currentFilter)]);
    } catch (err) {
      detailError.textContent = err.message;
      detailError.hidden = false;
      completeBtn.disabled = false;
    }
  });
}

async function submitCreateTask() {
  const title       = document.getElementById('ct-title').value.trim();
  const description = document.getElementById('ct-desc').value.trim();
  const tags        = document.getElementById('ct-tags').value.trim();
  const due_date    = document.getElementById('ct-due').value;        // "" or "YYYY-MM-DD"
  const assigneeVal = document.getElementById('ct-assignee').value;   // "" or "42"

  const body = { title };
  if (description)        body.description = description;
  if (tags)               body.tags        = tags;
  if (due_date)           body.due_date    = due_date;
  if (assigneeVal !== '') body.assignee_id = Number(assigneeVal);

  const errorEl   = document.getElementById('create-error');
  const submitBtn = document.querySelector('#form-create-task button[type="submit"]');

  errorEl.hidden = true;
  submitBtn.disabled = true;

  try {
    await api.post('/tasks', body);
    const createDialog = document.getElementById('modal-create-task');
    modal.closeModal(createDialog);
    document.getElementById('form-create-task').reset();
    await Promise.all([loadStats(), loadTasks(currentFilter)]);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  } finally {
    submitBtn.disabled = false;
  }
}

async function submitUpdateTask(taskId) {
  const body = {};
  body.title       = document.getElementById('et-title').value.trim();
  body.description = document.getElementById('et-desc').value.trim();
  body.tags        = document.getElementById('et-tags').value.trim();
  const dueVal     = document.getElementById('et-due').value;
  body.due_date    = dueVal === '' ? null : dueVal;
  const assigneeVal = document.getElementById('et-assignee').value;
  if (assigneeVal !== '') body.assignee_id = Number(assigneeVal);

  const errorEl   = document.getElementById('edit-error');
  const submitBtn = document.querySelector('#form-edit-task button[type="submit"]');
  errorEl.hidden   = true;
  submitBtn.disabled = true;

  try {
    const task = await api.patch(`/tasks/${taskId}`, body);
    const { html, title } = render.renderTaskDetail(task, usersMap);
    const detailDialog = document.getElementById('modal-task-detail');
    const detailBody   = document.getElementById('detail-body');
    const detailError  = document.getElementById('detail-error');

    document.getElementById('detail-title').textContent = title;
    detailBody.innerHTML = html;
    document.getElementById('detail-edit-form').hidden = true;
    detailBody.hidden = false;
    document.getElementById('btn-edit-task').hidden = false;
    render.renderEditForm(task, usersMap);

    _wireCompleteButton(detailBody, taskId, detailDialog, detailError);
    await Promise.all([loadStats(), loadTasks(currentFilter)]);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  } finally {
    submitBtn.disabled = false;
  }
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
    loadTasks(currentFilter)
      .then(() => loadStats())
      .catch(err => showGlobalError(err.message));
  });

  document.getElementById('btn-clear-filter').addEventListener('click', () => {
    document.getElementById('filter-form').reset();
    currentFilter = {};
    loadTasks({})
      .then(() => loadStats())
      .catch(err => showGlobalError(err.message));
  });

  // Global error banner
  document.getElementById('btn-dismiss-error').addEventListener('click', () => {
    document.getElementById('error-banner').hidden = true;
  });

  // Create task modal
  const createDialog = document.getElementById('modal-create-task');
  const btnNewTask   = document.getElementById('btn-new-task');

  btnNewTask.addEventListener('click', () => {
    modal.openModal(createDialog, btnNewTask);
  });

  document.getElementById('btn-cancel-create').addEventListener('click', () => {
    modal.closeModal(createDialog);
  });

  document.getElementById('form-create-task').addEventListener('submit', e => {
    e.preventDefault();
    submitCreateTask();
  });

  // Task detail modal
  const detailDialog = document.getElementById('modal-task-detail');

  document.getElementById('btn-close-detail').addEventListener('click', () => {
    document.getElementById('detail-edit-form').hidden = true;
    document.getElementById('detail-body').hidden      = false;
    document.getElementById('btn-edit-task').hidden    = true;
    modal.closeModal(detailDialog);
  });

  document.getElementById('btn-edit-task').addEventListener('click', () => {
    document.getElementById('detail-body').hidden      = true;
    document.getElementById('btn-edit-task').hidden    = true;
    document.getElementById('detail-edit-form').hidden = false;
    document.getElementById('edit-error').hidden       = true;
    document.getElementById('et-title').focus();
  });

  document.getElementById('btn-cancel-edit').addEventListener('click', () => {
    document.getElementById('detail-edit-form').hidden = true;
    document.getElementById('detail-body').hidden      = false;
    document.getElementById('btn-edit-task').hidden    = false;
  });

  document.getElementById('form-edit-task').addEventListener('submit', async e => {
    e.preventDefault();
    await submitUpdateTask(currentDetailTaskId);
  });

  // Initial load
  loadUsers()
    .then(() => Promise.all([loadStats(), loadTasks({})]))
    .catch(err => showGlobalError(err.message));
});

function showGlobalError(msg) {
  const banner = document.getElementById('error-banner');
  document.getElementById('error-banner-msg').textContent = msg;
  banner.hidden = false;
  setTimeout(() => { banner.hidden = true; }, 5000);
}
