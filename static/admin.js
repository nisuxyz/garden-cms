// Garden CMS — admin UI glue.
// Loaded as a single ES module; safe to run on every admin page.
//
// Responsibilities:
//   1. Attach the CSRF cookie to every outbound HTMX request as `x-csrftoken`.
//   2. Initialize CodeJar + Prism for every [data-editor] element.
//   3. Wire the live preview fetch when an editor carries data-preview-type.
//   4. Provide shared event delegation for media pickers, settings toggles,
//      logout, image-value mirrors, and site-head preset insertion.
//   5. Mark the current sidebar item via aria-current.
//   6. Toggle the mobile admin nav.
//
// Everything is wrapped in DOMContentLoaded; the module is idempotent.

document.addEventListener('DOMContentLoaded', () => {
  initCsrfBridge();
  initSidebarCurrent();
  initMobileNav();
  initEditors();
  initMediaPicker();
  initImageMirror();
  initStorageBackendToggle();
  initSavedPulse();
});

// ── 0. htmx config ──────────────────────────────────────────
// htmx 2.x ships with withCredentials=false by default. That means
// the browser omits cookies on the XHR/fetch requests htmx issues,
// which makes the CSRF middleware reject every htmx POST with 403.
// Run this *before* DOMContentLoaded — we need to set the flag before
// any user interaction can fire an htmx request.
//
// The setter is idempotent and harmless if htmx hasn't loaded yet
// (the `if (window.htmx)` short-circuits). The same htmx instance is
// reconfigured when it eventually finishes loading.
(function configureHtmx() {
  function set() {
    if (window.htmx) {
      window.htmx.config.withCredentials = true;
      return true;
    }
    return false;
  }
  if (set()) return;
  // Poll briefly until htmx has loaded. Cap at 5s to avoid spinning
  // forever on a failed CDN load.
  let waited = 0;
  const t = setInterval(() => {
    if (set() || waited > 5000) clearInterval(t);
    waited += 50;
  }, 50);
})();

// ── 1. CSRF ─────────────────────────────────────────────────

function readCsrfToken() {
  // Prefer the meta tag — it's set server-side at render time and
  // is always readable, even if the csrftoken cookie was set
  // HttpOnly by a previous version of the app. Fall back to the
  // cookie for backwards compatibility.
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;
  const m = document.cookie.match(/(?:^|;)\s*csrftoken=([^;]+)/);
  return m ? m[1] : null;
}

function initCsrfBridge() {
  document.body.addEventListener('htmx:configRequest', (evt) => {
    const token = readCsrfToken();
    if (token) evt.detail.headers['x-csrftoken'] = token;
  });
}

// ── 2. Sidebar aria-current ─────────────────────────────────

function initSidebarCurrent() {
  const here = location.pathname.replace(/\/+$/, '') || '/';
  document.querySelectorAll('aside.admin-sidebar nav a').forEach((a) => {
    const target = (a.getAttribute('href') || '').replace(/\/+$/, '') || '/';
    if (target === here || (target !== '/' && here.startsWith(target + '/'))) {
      a.setAttribute('aria-current', 'page');
    }
  });
}

// ── 3. Mobile nav ───────────────────────────────────────────

function initMobileNav() {
  const button = document.querySelector('.admin-header__menu-button');
  if (!button) return;
  button.addEventListener('click', () => {
    const open = document.body.classList.toggle('admin-nav-open');
    button.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.body.classList.contains('admin-nav-open')) {
      document.body.classList.remove('admin-nav-open');
      button.setAttribute('aria-expanded', 'false');
    }
  });
  document.body.addEventListener('click', (e) => {
    if (!document.body.classList.contains('admin-nav-open')) return;
    const sidebar = document.querySelector('aside.admin-sidebar');
    if (sidebar && !sidebar.contains(e.target) && !button.contains(e.target)) {
      document.body.classList.remove('admin-nav-open');
      button.setAttribute('aria-expanded', 'false');
    }
  });
}

// ── 4. CodeJar editor ───────────────────────────────────────

async function initEditors() {
  const editorNodes = document.querySelectorAll('[data-editor]');
  if (editorNodes.length === 0) return;
  const { CodeJar } = await import('https://unpkg.com/codejar/dist/codejar.js');
  const { withLineNumbers } = await import('https://unpkg.com/codejar-linenumbers/es/index.js');
  editorNodes.forEach((el) => setupEditor(el, CodeJar, withLineNumbers));
}

function setupEditor(el, CodeJar, withLineNumbers) {
  const target = document.getElementById(el.dataset.target);
  if (!target) return;
  const lang = el.dataset.lang || 'jinja2';
  const previewType = el.dataset.previewType || null;
  const previewFrameId = el.dataset.preview || null;

  const highlight = (editor) => {
    const code = editor.textContent;
    const grammar = (window.Prism && window.Prism.languages[lang]) || null;
    if (grammar) {
      // Prism.highlight escapes all source text and only emits its own
      // <span class="token-*"> markup, so innerHTML assignment is safe here.
      editor.innerHTML = window.Prism.highlight(code, grammar, lang);
    } else {
      editor.textContent = code;
    }
  };

  el.classList.add('language-' + lang);

  const jar = CodeJar(el, withLineNumbers(highlight), { tab: '  ', spellcheck: false });
  jar.onUpdate((code) => {
    target.value = code;
    const frame = previewFrameId && document.getElementById(previewFrameId);
    if (frame && previewType) {
      clearTimeout(el._debounce);
      el._debounce = setTimeout(() => {
        const form = new FormData();
        form.append('source', code);
        form.append('type', previewType);
        const headers = {};
        const token = readCsrfToken();
        if (token) headers['x-csrftoken'] = token;
        fetch('/admin/preview', { method: 'POST', body: form, headers })
          .then((r) => r.text())
          .then((html) => { frame.srcdoc = html; });
      }, 400);
    }
  });
  jar.updateCode(target.value);
  el._jar = jar;
}

// ── 5. Media picker (insert into editor) ────────────────────

function initMediaPicker() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-insert-media]');
    if (!btn) return;
    const editorSelector = btn.getAttribute('data-target-editor');
    if (!editorSelector) return;
    const editor = document.querySelector(editorSelector);
    if (!editor || !editor._jar) return;
    const filename = btn.getAttribute('data-insert-media') || '';
    const snippet = `<img src="{{ media_url('${filename}') }}" alt="" />`;
    editor._jar.updateCode(editor.textContent + snippet);
  });
}

// ── 6. Image value mirror (select → input) ─────────────────

function initImageMirror() {
  document.addEventListener('change', (e) => {
    const sel = e.target;
    if (!(sel instanceof HTMLSelectElement)) return;
    if (!sel.hasAttribute('data-mirror')) return;
    const target = document.getElementById(sel.getAttribute('data-mirror'));
    if (target && sel.value) {
      target.value = sel.value;
      sel.selectedIndex = 0;
    }
  });
}

// ── 7. Storage backend toggle (settings page) ──────────────

function initStorageBackendToggle() {
  const sel = document.getElementById('storage-backend');
  if (!sel) return;
  const update = () => {
    const fields = document.getElementById('s3-fields');
    if (fields) fields.hidden = sel.value !== 's3';
  };
  sel.addEventListener('change', update);
  update();
}

// ── 8. Saved! pulse on successful HTMX save ────────────────

function initSavedPulse() {
  document.body.addEventListener('htmx:afterRequest', (evt) => {
    if (evt.target && evt.target.hasAttribute && evt.target.hasAttribute('data-saved-target')) {
      const btn = document.getElementById(evt.target.getAttribute('data-saved-target'));
      if (btn) {
        const original = btn.textContent;
        btn.textContent = 'Saved';
        btn.setAttribute('data-save-pulse', '');
        setTimeout(() => {
          btn.textContent = original;
          btn.removeAttribute('data-save-pulse');
        }, 1800);
      }
    }
  });
}