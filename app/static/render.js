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

  // Title button
  const btn = document.createElement('button');
  btn.className = 'task-title-btn';
  btn.dataset.taskId = task.id;
  btn.textContent = task.title;
  li.appendChild(btn);

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
  li.appendChild(badge);

  // Tags
  if (task.tags && task.tags.length > 0) {
    const tagsSpan = document.createElement('span');
    tagsSpan.className = 'tags';
    for (const tag of task.tags) {
      const tagSpan = document.createElement('span');
      tagSpan.className = 'tag';
      tagSpan.textContent = tag;
      tagsSpan.appendChild(tagSpan);
    }
    li.appendChild(tagsSpan);
  }

  // Due date
  if (task.due_date) {
    const dueSpan = document.createElement('span');
    dueSpan.textContent = 'Due: ' + fmtDate(task.due_date);
    if (isOverdue) dueSpan.classList.add('overdue-date');
    li.appendChild(dueSpan);
  }

  // Assignee
  const assigneeSpan = document.createElement('span');
  assigneeSpan.textContent = (task.assignee_id && usersMap.get(task.assignee_id))
    ? usersMap.get(task.assignee_id)
    : 'Unassigned';
  li.appendChild(assigneeSpan);

  return li;
}

export function renderTaskDetail(task, usersMap) { /* TODO M5 */ }
export function renderEditForm(task, usersMap)   { /* TODO M6 */ }
