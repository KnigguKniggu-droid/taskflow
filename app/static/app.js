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

    // When a filter is active, derive stat-card counts from the fetched subset
    // so the numbers match what the user sees.  Without a filter, fetch
    // authoritative server totals directly — do NOT rely on callers to call
    // loadStats() separately, because that races with and overwrites filtered
    // counts when a filter is active.
    const isFiltered = Object.keys(params).length > 0;
    if (isFiltered) {
      render.renderFilteredStats(data.tasks);
      document.getElementById('stats-note').textContent =
        'Counts reflect the current filter, not all tasks.';
    } else {
      document.getElementById('stats-note').textContent = '';
      // Fetch global totals now that we know no filter is active.
      loadStats();
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
  const activitySection = document.getElementById('detail-activity');

  // Reset to read view
  detailTitle.textContent = '…';
  detailBody.innerHTML    = '';
  detailError.hidden      = true;
  editForm.hidden         = true;
  detailBody.hidden       = false;
  btnEditTask.hidden      = true;
  activitySection.hidden  = true;

  modal.openModal(detailDialog, returnEl);

  try {
    // Fetch task and activity in parallel
    const [task, activityData] = await Promise.allSettled([
      api.get(`/tasks/${taskId}`),
      api.get(`/tasks/${taskId}/activity`),
    ]);

    if (task.status === 'rejected') throw task.reason;

    const taskValue = task.value;
    const { html, title } = render.renderTaskDetail(taskValue, usersMap);
    detailTitle.textContent  = title;
    detailBody.innerHTML     = html;
    currentDetailTaskId      = taskValue.id;
    btnEditTask.hidden        = false;
    render.renderEditForm(taskValue, usersMap);

    // Wire status dropdown if present
    _wireStatusDropdown(detailBody, taskId, detailDialog, detailError);

    // Wire legacy "Mark Complete" button if present (graceful degradation)
    _wireCompleteButton(detailBody, taskId, detailDialog, detailError);

    // Render activity timeline
    const activities = activityData.status === 'fulfilled'
      ? (activityData.value.activity || [])
      : [];
    render.renderActivityTimeline(activities);
  } catch (err) {
    detailError.textContent = err.message;
    detailError.hidden = false;
  }
}

function _wireStatusDropdown(detailBody, taskId, detailDialog, detailError) {
  const sel = detailBody.querySelector('.status-select');
  if (!sel) return;
  sel.addEventListener('change', async () => {
    const newStatus = sel.value;
    if (!newStatus) return;
    sel.disabled = true;
    try {
      await api.patch(`/tasks/${taskId}`, { status: newStatus });
      modal.closeModal(detailDialog);
      await loadTasks(currentFilter);
    } catch (err) {
      detailError.textContent = err.message;
      detailError.hidden = false;
      sel.disabled = false;
      sel.value = '';
    }
  });
}

function _wireCompleteButton(detailBody, taskId, detailDialog, detailError) {
  const completeBtn = detailBody.querySelector('#btn-complete-task');
  if (!completeBtn) return;
  completeBtn.addEventListener('click', async () => {
    completeBtn.disabled = true;
    try {
      await api.post(`/tasks/${taskId}/complete`, {});
      modal.closeModal(detailDialog);
      await loadTasks(currentFilter);
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
    await loadTasks(currentFilter);
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
  // Always include assignee_id so that selecting "Unassigned" (value="")
  // sends null and clears the field.  Omitting the key would leave an
  // existing assignee unchanged — the user would have no way to unset it.
  const assigneeVal = document.getElementById('et-assignee').value;
  body.assignee_id = assigneeVal !== '' ? Number(assigneeVal) : null;

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
    document.getElementById('btn-close-detail').hidden = false;  // restore Close after save
    render.renderEditForm(task, usersMap);

    _wireStatusDropdown(detailBody, taskId, detailDialog, detailError);
    _wireCompleteButton(detailBody, taskId, detailDialog, detailError);

    // Refresh activity after edit
    try {
      const actData = await api.get(`/tasks/${taskId}/activity`);
      render.renderActivityTimeline(actData.activity || []);
    } catch (_) {
      // activity is non-critical; ignore errors
    }

    await loadTasks(currentFilter);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
    // Restore the Close button so the user can dismiss the dialog even after
    // a save failure.  (It was hidden when Edit mode was entered.)
    document.getElementById('btn-close-detail').hidden = false;
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
    loadTasks(currentFilter).catch(err => showGlobalError(err.message));
  });

  document.getElementById('btn-clear-filter').addEventListener('click', () => {
    document.getElementById('filter-form').reset();
    currentFilter = {};
    loadTasks({}).catch(err => showGlobalError(err.message));
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
    document.getElementById('btn-close-detail').hidden = true;   // hide Close while editing
    document.getElementById('detail-edit-form').hidden = false;
    document.getElementById('edit-error').hidden       = true;
    document.getElementById('et-title').focus();
  });

  document.getElementById('btn-cancel-edit').addEventListener('click', () => {
    document.getElementById('detail-edit-form').hidden = true;
    document.getElementById('detail-body').hidden      = false;
    document.getElementById('btn-edit-task').hidden    = false;
    document.getElementById('btn-close-detail').hidden = false;  // restore Close on cancel
  });

  document.getElementById('form-edit-task').addEventListener('submit', async e => {
    e.preventDefault();
    await submitUpdateTask(currentDetailTaskId);
  });

  // Initial load — loadTasks({}) calls loadStats() internally (no filter active).
  loadUsers()
    .then(() => loadTasks({}))
    .catch(err => showGlobalError(err.message));
});

function showGlobalError(msg) {
  const banner = document.getElementById('error-banner');
  document.getElementById('error-banner-msg').textContent = msg;
  banner.hidden = false;
  setTimeout(() => { banner.hidden = true; }, 5000);
}
