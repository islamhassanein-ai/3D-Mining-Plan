// Lightweight, dependency-free toast notifications -- a professional,
// non-blocking replacement for alert() and scattered inline status text.
// Stacks bottom-right, slides in, auto-dismisses (errors linger longer and
// can be dismissed manually). The container is an aria-live region so
// screen readers announce messages.
class ToastManager {
  constructor() {
    this.container = null;
    this.injectStyles();
  }

  _ensureContainer() {
    if (this.container && document.body.contains(this.container)) return;
    const el = document.createElement('div');
    el.className = 'toast-container';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    document.body.appendChild(el);
    this.container = el;
  }

  injectStyles() {
    if (document.getElementById('toast-styles')) return;
    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = `
      .toast-container {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-width: 360px;
        pointer-events: none;
      }
      .toast {
        pointer-events: auto;
        display: flex;
        align-items: flex-start;
        gap: 10px;
        background: rgba(16, 24, 40, 0.96);
        border: 1px solid var(--border-light, #223049);
        border-left: 3px solid var(--gold, #d4af37);
        border-radius: 8px;
        padding: 11px 12px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
        backdrop-filter: blur(8px);
        color: var(--text-main, #e8edf5);
        font-size: 12.5px;
        line-height: 1.45;
        opacity: 0;
        transform: translateX(24px);
        transition: opacity 0.2s ease, transform 0.2s ease;
      }
      .toast.show { opacity: 1; transform: translateX(0); }
      .toast.hide { opacity: 0; transform: translateX(24px); }
      .toast.success { border-left-color: #10b981; }
      .toast.error   { border-left-color: #ef4444; }
      .toast.warning { border-left-color: #f59e0b; }
      .toast.info    { border-left-color: var(--gold, #d4af37); }
      .toast-icon { flex-shrink: 0; width: 16px; height: 16px; margin-top: 1px; }
      .toast.success .toast-icon { color: #34d399; }
      .toast.error   .toast-icon { color: #f87171; }
      .toast.warning .toast-icon { color: #fbbf24; }
      .toast.info    .toast-icon { color: var(--gold-soft, #e8c76b); }
      .toast-body { flex: 1; min-width: 0; }
      .toast-title { font-weight: 700; margin-bottom: 1px; }
      .toast-msg { color: var(--text-muted, #93a2ba); word-wrap: break-word; }
      .toast-close {
        flex-shrink: 0;
        background: transparent;
        border: none;
        color: var(--text-faint, #5f7091);
        cursor: pointer;
        font-size: 15px;
        line-height: 1;
        padding: 0 2px;
      }
      .toast-close:hover { color: var(--text-main, #e8edf5); }
    `;
    document.head.appendChild(style);
  }

  _icon(type) {
    const paths = {
      success: 'M9,20.42L2.79,14.21L5.62,11.38L9,14.77L18.88,4.88L21.71,7.71L9,20.42Z',
      error: 'M13,13H11V7H13M13,17H11V15H13M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z',
      warning: 'M13,14H11V10H13M13,18H11V16H13M1,21H23L12,2L1,21Z',
      info: 'M13,9H11V7H13M13,17H11V11H13M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z'
    };
    return `<svg class="toast-icon" viewBox="0 0 24 24"><path fill="currentColor" d="${paths[type] || paths.info}"/></svg>`;
  }

  show(message, { type = 'info', title = null, duration = null } = {}) {
    this._ensureContainer();
    if (duration === null) duration = type === 'error' ? 8000 : 4000;

    const titles = { success: 'Success', error: 'Error', warning: 'Warning', info: 'Notice' };
    const heading = title || titles[type] || 'Notice';

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      ${this._icon(type)}
      <div class="toast-body">
        <div class="toast-title">${heading}</div>
        <div class="toast-msg"></div>
      </div>
      <button class="toast-close" aria-label="Dismiss">&times;</button>
    `;
    // Assign message as text (not HTML) so user/error content can't inject markup.
    toast.querySelector('.toast-msg').textContent = message;

    const dismiss = () => {
      toast.classList.add('hide');
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 220);
    };
    toast.querySelector('.toast-close').addEventListener('click', dismiss);

    this.container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));

    if (duration > 0) setTimeout(dismiss, duration);
    return dismiss;
  }

  success(msg, opts = {}) { return this.show(msg, { ...opts, type: 'success' }); }
  error(msg, opts = {}) { return this.show(msg, { ...opts, type: 'error' }); }
  warning(msg, opts = {}) { return this.show(msg, { ...opts, type: 'warning' }); }
  info(msg, opts = {}) { return this.show(msg, { ...opts, type: 'info' }); }
}

export const toast = new ToastManager();
