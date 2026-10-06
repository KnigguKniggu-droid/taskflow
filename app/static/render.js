// render.js — Pure DOM-building functions

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function fmtDate(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function renderStatCards(stats) {
  document.getElementById('stat-total').textContent     = stats.total;
  document.getElementById('stat-open').textContent      = stats.open;
  document.getElementById('stat-overdue').textContent   = stats.overdue;
  document.getElementById('stat-completed').textContent = stats.completed;
}

export function populateUserSelect(users, selectEl, allLabel = '— All —') {
  selectEl.innerHTML = '';
  const defaultOpt = document.createElement('option');
  defaultOpt.value = '';
  defaultOpt.textContent = allLabel;
  selectEl.appendChild(defaultOpt);
  for (const user of users) {
    const opt = document.createElement('option');
    opt.value = user.id;
    opt.textContent = user.name;
    selectEl.appendChild(opt);
  }
}

export function renderTask(task, usersMap) {
  const today = todayISO();
  const isCompleted = task.completed;
  const isOverdue = !isCompleted && task.due_date && task.due_date < today;

  const li = document.createElement('li');

  // ── Row 1: title ────────────────────────────────────────────────────
  const titleRow = document.createElement('div');
  titleRow.className = 'task-row-title';

  const btn = document.createElement('button');
  btn.className = 'task-title-btn';
  btn.dataset.taskId = task.id;
  btn.textContent = task.title;
  titleRow.appendChild(btn);
  li.appendChild(titleRow);

  // ── Row 2: badge · tags · due date · assignee ────────────────────────
  const metaRow = document.createElement('div');
  metaRow.className = 'task-row-meta';

  // Status badge
  const badge = document.createElement('span');
  if (isCompleted) {
    badge.className = 'badge-completed';
    badge.textContent = 'Completed';
  } else if (isOverdue) {
    badge.className = 'badge-overdue';
    badge.textContent = 'Overdue';
  } else {
    badge.className = 'badge-open';
    badge.textContent = 'Open';
  }
  metaRow.appendChild(badge);

  // Tags
  if (task.tags && task.tags.length > 0) {
    for (const tag of task.tags) {
      const tagSpan = document.createElement('span');
      tagSpan.className = 'tag';
      tagSpan.textContent = tag;
      metaRow.appendChild(tagSpan);
    }
  }

  // Due date
  if (task.due_date) {
    const dueSpan = document.createElement('span');
    dueSpan.textContent = 'Due: ' + fmtDate(task.due_date);
    if (isOverdue) dueSpan.classList.add('overdue-date');
    metaRow.appendChild(dueSpan);
  }

  // Assignee
  const assigneeSpan = document.createElement('span');
  assigneeSpan.textContent = (task.assignee_id && usersMap.get(task.assignee_id))
    ? usersMap.get(task.assignee_id)
    : 'Unassigned';
  metaRow.appendChild(assigneeSpan);

  li.appendChild(metaRow);
  return li;
}

/**
 * Derive summary counts from an already-fetched task array and update the
 * stat cards.  Used when a filter is active so the cards reflect the visible
 * subset rather than global totals.
 */
export function renderFilteredStats(tasks) {
  const today = todayISO();
  let open = 0, completed = 0, overdue = 0;
  for (const t of tasks) {
    if (t.completed) {
      completed++;
    } else {
      open++;
      if (t.due_date && t.due_date < today) overdue++;
    }
  }
  document.getElementById('stat-total').textContent     = tasks.length;
  document.getElementById('stat-open').textContent      = open;
  document.getElementById('stat-overdue').textContent   = overdue;
  document.getElementById('stat-completed').textContent = completed;
}

export function renderTaskDetail(task, usersMap) {
  const today = todayISO();
  const isCompleted = task.completed;
  const isOverdue = !isCompleted && task.due_date && task.due_date < today;

  // Status badge
  let statusBadge;
  if (isCompleted) {
    statusBadge = '<span class="badge-completed">Completed</span>';
  } else if (isOverdue) {
    statusBadge = '<span class="badge-overdue">Overdue</span>';
  } else {
    statusBadge = '<span class="badge-open">Open</span>';
  }

  // Description
  const descHtml = task.description
    ? escHtml(task.description)
    : '<span class="muted">—</span>';

  // Tags
  let tagsHtml;
  if (task.tags && task.tags.length > 0) {
    tagsHtml = task.tags.map(t => `<span class="tag">${escHtml(t)}</span>`).join(' ');
  } else {
    tagsHtml = '<span class="muted">None</span>';
  }

  // Due date
  let dueDateHtml;
  if (task.due_date) {
    const formatted = fmtDate(task.due_date);
    dueDateHtml = isOverdue
      ? `<span class="overdue-date">${escHtml(formatted)}</span>`
      : escHtml(formatted);
  } else {
    dueDateHtml = '<span class="muted">None</span>';
  }

  // Assignee
  const assigneeName = (task.assignee_id && usersMap.get(task.assignee_id))
    ? escHtml(usersMap.get(task.assignee_id))
    : '<span class="muted">Unassigned</span>';

  // Created date
  const createdDate = escHtml(
    new Date(task.created_at).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
    })
  );

  // Complete button or completed badge
  const actionHtml = isCompleted
    ? '<span class="badge-completed">Completed</span>'
    : `<button id="btn-complete-task" class="btn-complete" data-task-id="${task.id}">Mark Complete</button>`;

  const html = `
    <dl class="task-detail-fields">
      <dt>Status</dt>
      <dd>${statusBadge}</dd>

      <dt>Description</dt>
      <dd>${descHtml}</dd>

      <dt>Tags</dt>
      <dd>${tagsHtml}</dd>

      <dt>Due Date</dt>
      <dd>${dueDateHtml}</dd>

      <dt>Assignee</dt>
      <dd>${assigneeName}</dd>

      <dt>Created</dt>
      <dd>${createdDate}</dd>
    </dl>
    <div class="detail-actions">${actionHtml}</div>
  `;

  return { html, title: task.title };
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function renderEditForm(task, usersMap) {
  document.getElementById('et-title').value = task.title;
  document.getElementById('et-desc').value  = task.description ?? '';
  document.getElementById('et-tags').value  = (task.tags ?? []).join(', ');
  document.getElementById('et-due').value   = task.due_date ?? '';

  const sel = document.getElementById('et-assignee');
  populateUserSelect(
    [...usersMap.entries()].map(([id, name]) => ({ id, name })),
    sel,
    'Unassigned'
  );
  sel.value = task.assignee_id ?? '';
}
