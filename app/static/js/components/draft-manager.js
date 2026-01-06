/**
 * Draft Manager Component
 *
 * Manages saving and loading calculator drafts to LocalStorage.
 * Supports multiple drafts with name, rename, delete, and auto-cleanup.
 *
 * Storage format:
 * {
 *   "zakat_drafts": [
 *     {
 *       "id": "uuid",
 *       "name": "My Draft",
 *       "created_at": "2026-01-05T12:00:00Z",
 *       "updated_at": "2026-01-05T14:30:00Z",
 *       "payload": { "v": 1, "data": {...} }
 *     }
 *   ]
 * }
 */

var DraftManager = (function() {
    'use strict';

    // Constants
    var STORAGE_KEY = 'zakat_drafts';
    var MAX_DRAFTS = 20;
    var SCHEMA_VERSION = 1;

    // State
    var container = null;
    var isListVisible = false;

    /**
     * Generate a UUID v4
     */
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0;
            var v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    /**
     * Get all drafts from LocalStorage
     * @returns {Array} Array of draft objects
     */
    function getDrafts() {
        try {
            var stored = localStorage.getItem(STORAGE_KEY);
            if (!stored) return [];
            var drafts = JSON.parse(stored);
            return Array.isArray(drafts) ? drafts : [];
        } catch (e) {
            console.error('DraftManager: Failed to read drafts', e);
            return [];
        }
    }

    /**
     * Save drafts to LocalStorage
     * @param {Array} drafts - Array of draft objects
     * @returns {boolean} Success status
     */
    function saveDrafts(drafts) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts));
            return true;
        } catch (e) {
            if (e.name === 'QuotaExceededError') {
                showError('Storage quota exceeded. Please delete some drafts.');
            } else {
                console.error('DraftManager: Failed to save drafts', e);
                showError('Failed to save draft. Please try again.');
            }
            return false;
        }
    }

    /**
     * Initialize the draft manager
     * @param {string} containerId - ID of the container element
     */
    function init(containerId) {
        container = document.getElementById(containerId);
        if (!container) {
            console.warn('DraftManager: Container not found:', containerId);
            return;
        }

        render();
        bindEvents();
    }

    /**
     * Save current calculator state as a new draft
     * @param {string} name - Name for the draft
     * @returns {Object|null} Saved draft or null on failure
     */
    function saveDraft(name) {
        if (typeof ZakatCalculator === 'undefined') {
            showError('Calculator not available.');
            return null;
        }

        var state = ZakatCalculator.getState();
        var drafts = getDrafts();
        var now = new Date().toISOString();

        var draft = {
            id: generateUUID(),
            name: name || 'Draft ' + (drafts.length + 1),
            created_at: now,
            updated_at: now,
            payload: {
                v: SCHEMA_VERSION,
                data: state
            }
        };

        // Add new draft at the beginning
        drafts.unshift(draft);

        // Enforce max drafts limit (remove oldest)
        while (drafts.length > MAX_DRAFTS) {
            drafts.pop();
        }

        if (saveDrafts(drafts)) {
            render();
            showSuccess('Draft saved successfully.');
            return draft;
        }

        return null;
    }

    /**
     * Load a draft by ID
     * @param {string} id - Draft ID
     * @returns {boolean} Success status
     */
    function loadDraft(id) {
        var drafts = getDrafts();
        var draft = drafts.find(function(d) { return d.id === id; });

        if (!draft) {
            showError('Draft not found.');
            return false;
        }

        if (typeof ZakatCalculator === 'undefined') {
            showError('Calculator not available.');
            return false;
        }

        // Handle schema versioning
        var payload = draft.payload;
        if (!payload || payload.v !== SCHEMA_VERSION) {
            showError('Incompatible draft version.');
            return false;
        }

        ZakatCalculator.setState(payload.data);
        hideList();
        showSuccess('Draft loaded: ' + draft.name);
        return true;
    }

    /**
     * Rename a draft
     * @param {string} id - Draft ID
     * @param {string} newName - New name for the draft
     * @returns {boolean} Success status
     */
    function renameDraft(id, newName) {
        if (!newName || !newName.trim()) {
            showError('Please enter a valid name.');
            return false;
        }

        var drafts = getDrafts();
        var draft = drafts.find(function(d) { return d.id === id; });

        if (!draft) {
            showError('Draft not found.');
            return false;
        }

        draft.name = newName.trim();
        draft.updated_at = new Date().toISOString();

        if (saveDrafts(drafts)) {
            render();
            showSuccess('Draft renamed.');
            return true;
        }

        return false;
    }

    /**
     * Delete a draft
     * @param {string} id - Draft ID
     * @returns {boolean} Success status
     */
    function deleteDraft(id) {
        var drafts = getDrafts();
        var index = drafts.findIndex(function(d) { return d.id === id; });

        if (index === -1) {
            showError('Draft not found.');
            return false;
        }

        drafts.splice(index, 1);

        if (saveDrafts(drafts)) {
            render();
            showSuccess('Draft deleted.');
            return true;
        }

        return false;
    }

    /**
     * Format a date for display
     * @param {string} isoDate - ISO date string
     * @returns {string} Formatted date
     */
    function formatDate(isoDate) {
        try {
            var date = new Date(isoDate);
            var now = new Date();
            var diff = now - date;
            var days = Math.floor(diff / (1000 * 60 * 60 * 24));

            if (days === 0) {
                return 'Today';
            } else if (days === 1) {
                return 'Yesterday';
            } else if (days < 7) {
                return days + ' days ago';
            } else {
                return date.toLocaleDateString();
            }
        } catch (e) {
            return '';
        }
    }

    /**
     * Render the draft list
     */
    function render() {
        if (!container) return;

        var drafts = getDrafts();

        var html = [
            '<div class="draft-list' + (isListVisible ? ' visible' : '') + '">',
            '  <div class="draft-list-header">',
            '    <span class="draft-list-title">Saved Drafts</span>',
            '    <button type="button" class="draft-list-close" aria-label="Close draft list">&times;</button>',
            '  </div>',
            '  <div class="draft-list-content">'
        ];

        if (drafts.length === 0) {
            html.push('    <div class="draft-empty">No saved drafts yet.</div>');
        } else {
            drafts.forEach(function(draft) {
                html.push(
                    '    <div class="draft-item" data-id="' + escapeHtml(draft.id) + '">',
                    '      <div class="draft-item-info">',
                    '        <span class="draft-item-name">' + escapeHtml(draft.name) + '</span>',
                    '        <span class="draft-item-date">' + formatDate(draft.updated_at) + '</span>',
                    '      </div>',
                    '      <div class="draft-item-actions">',
                    '        <button type="button" class="draft-action-btn draft-load-btn" title="Load draft">',
                    '          Load',
                    '        </button>',
                    '        <button type="button" class="draft-action-btn draft-rename-btn" title="Rename draft">',
                    '          Rename',
                    '        </button>',
                    '        <button type="button" class="draft-action-btn draft-delete-btn" title="Delete draft">',
                    '          Delete',
                    '        </button>',
                    '      </div>',
                    '    </div>'
                );
            });
        }

        html.push(
            '  </div>',
            '  <div class="draft-list-footer">',
            '    <span class="draft-count">' + drafts.length + ' / ' + MAX_DRAFTS + ' drafts</span>',
            '  </div>',
            '</div>'
        );

        container.innerHTML = html.join('\n');

        // Re-bind events after render
        bindListEvents();
    }

    /**
     * Bind events for save/load buttons
     */
    function bindEvents() {
        document.addEventListener('click', function(event) {
            var saveDraftBtn = event.target.closest('#save-draft-btn');
            if (saveDraftBtn) {
                event.preventDefault();
                promptSaveDraft();
                return;
            }

            var loadDraftBtn = event.target.closest('#load-draft-btn');
            if (loadDraftBtn) {
                event.preventDefault();
                toggleList();
                return;
            }
        });

        // Close list when clicking outside
        document.addEventListener('click', function(event) {
            if (isListVisible && container && !container.contains(event.target)) {
                var loadBtn = document.getElementById('load-draft-btn');
                if (!loadBtn || !loadBtn.contains(event.target)) {
                    hideList();
                }
            }
        });
    }

    /**
     * Bind events for draft list items
     */
    function bindListEvents() {
        if (!container) return;

        // Close button
        var closeBtn = container.querySelector('.draft-list-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function(event) {
                event.stopPropagation();
                hideList();
            });
        }

        // Draft item actions
        container.querySelectorAll('.draft-item').forEach(function(item) {
            var id = item.dataset.id;

            var loadBtn = item.querySelector('.draft-load-btn');
            if (loadBtn) {
                loadBtn.addEventListener('click', function(event) {
                    event.stopPropagation();
                    loadDraft(id);
                });
            }

            var renameBtn = item.querySelector('.draft-rename-btn');
            if (renameBtn) {
                renameBtn.addEventListener('click', function(event) {
                    event.stopPropagation();
                    promptRenameDraft(id);
                });
            }

            var deleteBtn = item.querySelector('.draft-delete-btn');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', function(event) {
                    event.stopPropagation();
                    confirmDeleteDraft(id);
                });
            }
        });
    }

    /**
     * Prompt user for draft name and save
     */
    function promptSaveDraft() {
        var name = prompt('Enter a name for this draft:', 'My Calculation');
        if (name !== null) {
            saveDraft(name.trim() || 'Untitled');
        }
    }

    /**
     * Prompt user for new draft name
     */
    function promptRenameDraft(id) {
        var drafts = getDrafts();
        var draft = drafts.find(function(d) { return d.id === id; });
        if (!draft) return;

        var newName = prompt('Enter new name:', draft.name);
        if (newName !== null && newName.trim()) {
            renameDraft(id, newName.trim());
        }
    }

    /**
     * Confirm draft deletion
     */
    function confirmDeleteDraft(id) {
        var drafts = getDrafts();
        var draft = drafts.find(function(d) { return d.id === id; });
        if (!draft) return;

        var confirmed = confirm('Delete "' + draft.name + '"? This cannot be undone.');
        if (confirmed) {
            deleteDraft(id);
        }
    }

    /**
     * Toggle the draft list visibility
     */
    function toggleList() {
        if (isListVisible) {
            hideList();
        } else {
            showList();
        }
    }

    /**
     * Show the draft list
     */
    function showList() {
        isListVisible = true;
        render();
    }

    /**
     * Hide the draft list
     */
    function hideList() {
        isListVisible = false;
        if (container) {
            var list = container.querySelector('.draft-list');
            if (list) {
                list.classList.remove('visible');
            }
        }
    }

    /**
     * Show success message
     */
    function showSuccess(message) {
        showNotification(message, 'success');
    }

    /**
     * Show error message
     */
    function showError(message) {
        showNotification(message, 'error');
    }

    /**
     * Show notification toast
     */
    function showNotification(message, type) {
        // Remove existing notifications
        var existing = document.querySelector('.draft-notification');
        if (existing) {
            existing.remove();
        }

        var notification = document.createElement('div');
        notification.className = 'draft-notification draft-notification-' + type;
        notification.textContent = message;
        document.body.appendChild(notification);

        // Trigger animation
        setTimeout(function() {
            notification.classList.add('visible');
        }, 10);

        // Auto-remove after 3 seconds
        setTimeout(function() {
            notification.classList.remove('visible');
            setTimeout(function() {
                notification.remove();
            }, 300);
        }, 3000);
    }

    /**
     * Escape HTML special characters
     */
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Public API
    return {
        init: init,
        saveDraft: saveDraft,
        loadDraft: loadDraft,
        renameDraft: renameDraft,
        deleteDraft: deleteDraft,
        getDrafts: getDrafts,
        render: render
    };
})();
