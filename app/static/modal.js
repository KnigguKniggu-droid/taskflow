// modal.js — Dialog lifecycle and focus management

const FOCUSABLE = ':is(button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"]))';

const _state = new WeakMap(); // dialogEl → { returnFocusEl, trapHandler }

export function openModal(dialogEl, returnFocusEl) {
  const trapHandler = e => _trapFocus(e, dialogEl);
  _state.set(dialogEl, { returnFocusEl, trapHandler });
  dialogEl.addEventListener('keydown', trapHandler);
  dialogEl.showModal();
  // focus first focusable child
  const first = dialogEl.querySelector(FOCUSABLE);
  if (first) first.focus();
}

export function closeModal(dialogEl) {
  const s = _state.get(dialogEl);
  if (s) {
    dialogEl.removeEventListener('keydown', s.trapHandler);
    _state.delete(dialogEl);
    dialogEl.close();
    if (s.returnFocusEl) s.returnFocusEl.focus();
  } else {
    dialogEl.close();
  }
}

function _trapFocus(e, dialogEl) {
  if (e.key !== 'Tab') return;
  const focusable = [...dialogEl.querySelectorAll(FOCUSABLE)];
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
}
