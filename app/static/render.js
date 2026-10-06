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

// Map status → { cssClass, label }
const STATUS_BADGE = {
  open:        { cssClass: 'badge-open',        label: 'Open'        },
  in_progress: { cssClass: 'badge-in-progress', label: 'In Progress' },
  blocked:     { cssClass: 'badge-blocked',      label: 'Blocked'     },
  completed:   { cssClass: 'badge-completed',    label: 'Completed'   },
};

// Valid next states for each status (mirrors server VALID_TRANSITIONS)
const NEXT_STATES = {
  open:        ['in_progress', 'blocked', 'completed'],
  in_progress: ['open', 'blocked', 'completed'],
  blocked:     ['open', 'in_progress', 'completed'],
  completed:   ['open'],
};

const ACTIVITY_LABELS = {
  created:         'Created',
  status_changed:  'Status changed',
  reassigned:      'Reassigned',
  due_date_changed:'Due date changed',
  details_edited:  'Details edited',
};

export function renderStatCards(stats) {
  document.getElementById('stat-total').textContent       = stats.total;
  document.getElementById('stat-open').textContent        = stats.open;
  document.getElementById('stat-in-progress').textContent = stats.in_progress ?? '—';
  document.getElementById('stat-blocked').textContent     = stats.blocked ?? '—';
  document.getElementById('stat-overdue').textContent     = stats.overdue;
  document.getElementById('stat-completed').textContent   = stats.completed;
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

function _statusBadgeEl(task) {
  const today = todayISO();
  const isOverdue = task.status !== 'completed' && task.due_date && task.due_date < today;
  const badge = document.createElement('span');
  if (isOverdue) {
    badge.className = 'badge-overdue';
    badge.textContent = 'Overdue';
  } else {
    const info = STATUS_BADGE[task.status] || STATUS_BADGE.open;
    badge.className = info.cssClass;
    badge.textContent = info.label;
  }
  return badge;
}

export function renderTask(task, usersMap) {
  const today = todayISO();
  const isOverdue = task.status !== 'completed' && task.due_date && task.due_date < today;

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

  metaRow.appendChild(_statusBadgeEl(task));

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
  let open = 0, in_progress = 0, blocked = 0, completed = 0, overdue = 0;
  for (const t of tasks) {
    if (t.status === 'completed') {
      completed++;
    } else {
      if (t.status === 'in_progress') in_progress++;
      else if (t.status === 'blocked') blocked++;
      else open++;
      if (t.due_date && t.due_date < today) overdue++;
    }
  }
  document.getElementById('stat-total').textContent       = tasks.length;
  document.getElementById('stat-open').textContent        = open + in_progress + blocked;
  document.getElementById('stat-in-progress').textContent = in_progress;
  document.getElementById('stat-blocked').textContent     = blocked;
  document.getElementById('stat-overdue').textContent     = overdue;
  document.getElementById('stat-completed').textContent   = completed;
}

export function renderTaskDetail(task, usersMap) {
  const today = todayISO();
  const isOverdue = task.status !== 'completed' && task.due_date && task.due_date < today;

  // Status badge HTML
  let statusBadgeHtml;
  if (isOverdue) {
    statusBadgeHtml = '<span class="badge-overdue">Overdue</span>';
  } else {
    const info = STATUS_BADGE[task.status] || STATUS_BADGE.open;
    statusBadgeHtml = `<span class="${escHtml(info.cssClass)}">${escHtml(info.label)}</span>`;
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

  // Status action: dropdown of valid next states if status is known,
  // otherwise fall back to the legacy "Mark Complete" button for old servers.
  let actionHtml;
  if (task.status) {
    const nextStates = NEXT_STATES[task.status] || [];
    if (nextStates.length > 0) {
      const opts = nextStates
        .map(s => {
          const label = STATUS_BADGE[s] ? STATUS_BADGE[s].label : s;
          return `<option value="${escHtml(s)}">${escHtml(label)}</option>`;
        })
        .join('');
      actionHtml = `
        <div class="status-dropdown-row">
          <label for="status-select-${task.id}">Change status:</label>
          <select id="status-select-${task.id}" class="status-select" data-task-id="${task.id}">
            <option value="">— select —</option>
            ${opts}
          </select>
        </div>`;
    } else {
      // completed with no further transitions (shouldn't happen normally)
      actionHtml = `<span class="${escHtml((STATUS_BADGE[task.status] || STATUS_BADGE.completed).cssClass)}">${escHtml((STATUS_BADGE[task.status] || STATUS_BADGE.completed).label)}</span>`;
    }
  } else {
    // Graceful degradation: server does not yet return status
    actionHtml = task.completed
      ? '<span class="badge-completed">Completed</span>'
      : `<button id="btn-complete-task" class="btn-complete" data-task-id="${task.id}">Mark Complete</button>`;
  }

  const html = `
    <dl class="task-detail-fields">
      <dt>Status</dt>
      <dd>${statusBadgeHtml}</dd>

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

/**
 * Render the activity timeline into the #detail-activity section.
 * Pass an empty array to hide the section.
 */
export function renderActivityTimeline(activities) {
  const section = document.getElementById('detail-activity');
  const list    = document.getElementById('activity-list');

  if (!activities || activities.length === 0) {
    section.hidden = true;
    list.innerHTML = '';
    return;
  }

  list.innerHTML = '';
  for (const entry of activities) {
    const label = ACTIVITY_LABELS[entry.event] || entry.event;
    const timeStr = _fmtActivityTime(entry.created_at);

    const li = document.createElement('li');
    li.innerHTML = `
      <span class="activity-dot" aria-hidden="true">●</span>
      <div class="activity-content">
        <div class="activity-header">
          <span class="activity-label">${escHtml(label)}</span>
          <span class="activity-time">${escHtml(timeStr)}</span>
        </div>
        ${entry.detail ? `<div class="activity-detail">${escHtml(entry.detail)}</div>` : ''}
      </div>`;
    list.appendChild(li);
  }
  section.hidden = false;
}

function _fmtActivityTime(isoStr) {
  try {
    return new Date(isoStr).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return isoStr;
  }
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
