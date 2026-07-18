import { ApiClient } from '../services/api_client.js';

export class SharePanel {
  constructor(container, projectId) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.projectId = projectId;
    this.links = [];
    this.loading = false;

    this.init();
  }

  init() {
    this.injectStyles();
    this.loadShareLinks();
  }

  injectStyles() {
    if (document.getElementById('share-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'share-panel-styles';
    style.textContent = `
      .share-panel-card {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        color: #e2e8f0;
      }
      .share-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
      }
      .share-header h3 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: #f8fafc;
      }
      .share-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
        max-height: 240px;
        overflow-y: auto;
        margin-top: 12px;
        padding-right: 4px;
      }
      .share-item {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .share-item-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .share-token-url {
        font-family: monospace;
        font-size: 0.8rem;
        background: rgba(0, 0, 0, 0.3);
        padding: 4px 8px;
        border-radius: 4px;
        color: #3b82f6;
        cursor: pointer;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 70%;
      }
      .share-token-url:hover {
        background: rgba(59, 130, 246, 0.15);
      }
      .share-badge {
        font-size: 0.7rem;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
        text-transform: uppercase;
      }
      .badge-active {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
      }
      .badge-revoked {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
      }
      .badge-expired {
        background: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
      }
      .share-item-meta {
        font-size: 0.75rem;
        color: #94a3b8;
        display: flex;
        justify-content: space-between;
      }
      .share-actions {
        display: flex;
        gap: 8px;
        margin-top: 4px;
      }
      .btn-share-action {
        flex: 1;
        padding: 6px;
        font-size: 0.75rem;
        border-radius: 4px;
        border: none;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s ease;
      }
      .btn-revoke {
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.2);
      }
      .btn-revoke:hover:not(:disabled) {
        background: #ef4444;
        color: white;
      }
      .btn-renew {
        background: rgba(59, 130, 246, 0.1);
        color: #3b82f6;
        border: 1px solid rgba(59, 130, 246, 0.2);
      }
      .btn-renew:hover:not(:disabled) {
        background: #3b82f6;
        color: white;
      }
      .btn-share-action:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
    `;
    document.head.appendChild(style);
  }

  async loadShareLinks() {
    this.loading = true;
    this.render();
    try {
      this.links = await ApiClient.listShareLinks(this.projectId);
    } catch (err) {
      console.error(err);
    } finally {
      this.loading = false;
      this.render();
    }
  }

  getLinkStatus(link) {
    if (link.revoked_at) return 'revoked';
    const expires = new Date(link.expires_at);
    if (expires <= new Date()) return 'expired';
    return 'active';
  }

  async createLink() {
    try {
      await ApiClient.createShareLink(this.projectId);
      await this.loadShareLinks();
    } catch (err) {
      alert("Failed to create share link: " + err.message);
    }
  }

  async revokeLink(linkId) {
    try {
      await ApiClient.revokeShareLink(this.projectId, linkId);
      await this.loadShareLinks();
    } catch (err) {
      alert("Failed to revoke: " + err.message);
    }
  }

  async renewLink(linkId) {
    try {
      await ApiClient.renewShareLink(this.projectId, linkId);
      await this.loadShareLinks();
    } catch (err) {
      alert("Failed to renew: " + err.message);
    }
  }

  copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
      alert("Share URL copied to clipboard!");
    }).catch(err => {
      console.error('Failed to copy: ', err);
    });
  }

  render() {
    if (this.loading) {
      this.container.innerHTML = `
        <div class="share-panel-card" style="text-align:center;">
          <div class="loading-spinner" style="width:20px;height:20px;margin:0 auto 10px;"></div>
          Loading sharing dashboard...
        </div>
      `;
      return;
    }

    this.container.innerHTML = `
      <div class="share-panel-card">
        <div class="share-header">
          <h3>Share Prospect</h3>
          <button id="gen-share-btn" class="btn-primary" style="padding:6px 12px;font-size:0.8rem;">Generate Link</button>
        </div>
        
        <div class="share-list">
          ${this.links.length === 0 ? `
            <div style="font-size:0.8rem;color:#94a3b8;text-align:center;padding:20px 0;">
              No active share links. Generate one to invite colleagues.
            </div>
          ` : this.links.map(l => {
            const status = this.getLinkStatus(l);
            const expiresDate = new Date(l.expires_at).toLocaleString();
            
            // Construct the sharing URL matching where index.html is hosted
            const shareUrl = `${window.location.origin}${window.location.pathname}?share=${l.token}`;
            
            return `
              <div class="share-item">
                <div class="share-item-top">
                  <div class="share-token-url" title="Click to copy full link" data-url="${shareUrl}">
                    ${shareUrl}
                  </div>
                  <span class="share-badge badge-${status}">${status}</span>
                </div>
                <div class="share-item-meta">
                  <span>Expires: ${expiresDate}</span>
                </div>
                ${status === 'active' ? `
                  <div class="share-actions">
                    <button class="btn-share-action btn-renew" data-id="${l.id}">Renew (7d)</button>
                    <button class="btn-share-action btn-revoke" data-id="${l.id}">Revoke</button>
                  </div>
                ` : ''}
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;

    // Bind event handlers
    const genBtn = this.container.querySelector('#gen-share-btn');
    if (genBtn) {
      genBtn.onclick = () => this.createLink();
    }

    this.container.querySelectorAll('.share-token-url').forEach(el => {
      el.onclick = () => this.copyToClipboard(el.getAttribute('data-url'));
    });

    this.container.querySelectorAll('.btn-revoke').forEach(el => {
      el.onclick = () => this.revokeLink(el.getAttribute('data-id'));
    });

    this.container.querySelectorAll('.btn-renew').forEach(el => {
      el.onclick = () => this.renewLink(el.getAttribute('data-id'));
    });
  }
}
