// Saved camera views ("bookmarks").
//
// The four presets (Plan / Section N-S / Section E-W / Isometric) answer
// "show me a standard orientation". They cannot answer "put me back on the
// oblique view I use to show this vein to the client", which is the view a
// geologist actually returns to twenty times a day. This stores that view --
// orbit target plus camera position, which together pin angle, distance and
// centring exactly.
//
// Storage is localStorage, keyed per project, because a saved view is a
// personal habit rather than project data: it should not travel to whoever the
// project is shared with, and it should survive a page reload with no server
// round-trip. The cost is that views do not follow the user to another
// machine, which is the right trade for a bookmark.
//
// One view per project may be flagged as the startup view. When set, the
// project opens on it instead of on the automatic fit-to-data framing, and
// Reset Camera [R] returns there too -- "start me where I work" and "take me
// back there" are the same wish.

const STORAGE_PREFIX = 'camera_bookmarks:';
const MAX_BOOKMARKS = 20;

export class ViewBookmarks {
  /**
   * @param container  element (or id) to render the list into
   * @param viewport   object returned by init3DViewport
   * @param projectId  scopes the stored views; a falsy id disables persistence
   */
  constructor(container, viewport, projectId) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.viewport = viewport;
    this.projectId = projectId || null;
    this.views = this.load();
    if (this.container) {
      this.injectStyles();
      this.render();
    }
  }

  get storageKey() {
    return this.projectId ? `${STORAGE_PREFIX}${this.projectId}` : null;
  }

  load() {
    if (!this.storageKey) return [];
    try {
      const raw = localStorage.getItem(this.storageKey);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      // A corrupted entry must not stop the project from opening.
      return [];
    }
  }

  persist() {
    if (!this.storageKey) return;
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.views));
    } catch (err) {
      if (window.toast) window.toast.error('Could not save the view — browser storage is full.');
    }
  }

  /** Captures the live camera under `name`. Returns the stored view. */
  save(name) {
    const label = (name || '').trim() || `View ${this.views.length + 1}`;
    const pose = this.viewport.controls.getPose();
    const existing = this.views.find(v => v.name.toLowerCase() === label.toLowerCase());

    if (existing) {
      // Same name means "update this one". Silently adding a second entry with
      // an identical label would leave two indistinguishable rows.
      existing.target = pose.target;
      existing.position = pose.position;
    } else {
      if (this.views.length >= MAX_BOOKMARKS) {
        if (window.toast) window.toast.error(`Keep at most ${MAX_BOOKMARKS} saved views — delete one first.`);
        return null;
      }
      this.views.push({
        id: `v${Date.now()}${Math.floor(Math.random() * 1000)}`,
        name: label,
        target: pose.target,
        position: pose.position,
        startup: false,
      });
    }
    this.persist();
    this.render();
    return this.views.find(v => v.name.toLowerCase() === label.toLowerCase());
  }

  /** Moves the camera to a stored view. */
  apply(id) {
    const view = this.views.find(v => v.id === id);
    if (!view) return false;
    return this.viewport.controls.applyPose(view);
  }

  remove(id) {
    this.views = this.views.filter(v => v.id !== id);
    this.persist();
    this.render();
  }

  /** Flags one view as the startup view, or clears the flag if it was set. */
  toggleStartup(id) {
    const view = this.views.find(v => v.id === id);
    if (!view) return;
    const wasStartup = view.startup;
    this.views.forEach(v => { v.startup = false; });
    view.startup = !wasStartup;
    this.persist();
    this.render();
  }

  /**
   * Applies the startup view if one is flagged. Called after the scene has
   * loaded and framed itself, so a project with no startup view keeps the
   * automatic fit. Also re-anchors Reset Camera on the startup view.
   *
   * @returns true if a startup view was applied
   */
  applyStartup() {
    const view = this.views.find(v => v.startup);
    if (!view) return false;
    if (!this.viewport.controls.applyPose(view)) return false;
    // Reset Camera [R] should come back here, not to the auto-fit framing the
    // startup view was chosen to replace.
    this.viewport.controls.storeHome();
    return true;
  }

  injectStyles() {
    if (document.getElementById('view-bookmark-styles')) return;
    const style = document.createElement('style');
    style.id = 'view-bookmark-styles';
    style.textContent = `
      .vb-save-row { display: flex; gap: 6px; margin-bottom: 8px; }
      .vb-save-row input {
        flex: 1; min-width: 0; background: rgba(0,0,0,0.3);
        border: 1px solid var(--border-light, rgba(255,255,255,0.12));
        color: var(--text-main, #e8edf5); padding: 6px; border-radius: 6px; font-size: 0.75rem;
      }
      .vb-save-row input:focus { outline: none; border-color: var(--gold, #d4af37); }
      .vb-list { display: flex; flex-direction: column; }
      .vb-empty { font-size: 0.7rem; color: var(--text-muted, #8a97ad); line-height: 1.5; }
      .vb-row {
        display: flex; align-items: center; gap: 4px; padding: 4px 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
      }
      .vb-row:last-child { border-bottom: none; }
      .vb-go {
        flex: 1; min-width: 0; text-align: left; background: none; border: none;
        color: var(--text-main, #e8edf5); font-size: 0.75rem; padding: 3px 2px;
        cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .vb-go:hover { color: var(--gold, #d4af37); }
      .vb-icon {
        background: none; border: none; cursor: pointer; padding: 2px 4px;
        font-size: 0.8rem; line-height: 1; color: var(--text-muted, #8a97ad); flex-shrink: 0;
      }
      .vb-icon:hover { color: var(--text-main, #e8edf5); }
      .vb-icon.on { color: var(--gold, #d4af37); }
      .vb-icon.vb-del:hover { color: #f87171; }
    `;
    document.head.appendChild(style);
  }

  render() {
    if (!this.container) return;
    const rows = this.views.map(v => `
      <div class="vb-row">
        <button class="vb-go" data-go="${v.id}" title="Go to this view">${escapeHtml(v.name)}</button>
        <button class="vb-icon ${v.startup ? 'on' : ''}" data-startup="${v.id}"
                title="${v.startup ? 'Startup view — click to unset' : 'Open the project on this view'}">&#9733;</button>
        <button class="vb-icon vb-del" data-del="${v.id}" title="Delete this view">&times;</button>
      </div>
    `).join('');

    this.container.innerHTML = `
      <div class="vb-save-row">
        <input type="text" id="vb-name" placeholder="Name this view" maxlength="40">
        <button class="btn-small" id="vb-save">Save</button>
      </div>
      <div class="vb-list">
        ${rows || '<div class="vb-empty">No saved views yet. Orbit to the angle you want, type a name, and hit Save. The star marks the view the project opens on.</div>'}
      </div>
    `;

    const nameInput = this.container.querySelector('#vb-name');
    const saveView = () => {
      const saved = this.save(nameInput.value);
      if (saved && window.toast) window.toast(`Saved view "${saved.name}"`);
    };
    this.container.querySelector('#vb-save').onclick = saveView;
    nameInput.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); saveView(); } };

    this.container.querySelectorAll('[data-go]').forEach(btn => {
      btn.onclick = () => this.apply(btn.dataset.go);
    });
    this.container.querySelectorAll('[data-startup]').forEach(btn => {
      btn.onclick = () => this.toggleStartup(btn.dataset.startup);
    });
    this.container.querySelectorAll('[data-del]').forEach(btn => {
      btn.onclick = () => this.remove(btn.dataset.del);
    });
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
