// Small progressive enhancements. The site works without JavaScript.
(() => {
  // Mobile navigation
  const toggle = document.querySelector('.nav-toggle');
  if (toggle) {
    const setOpen = (open) => {
      toggle.setAttribute('aria-expanded', String(open));
      document.body.classList.toggle('nav-open', open);
    };
    toggle.addEventListener('click', () => setOpen(toggle.getAttribute('aria-expanded') !== 'true'));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
    matchMedia('(min-width: 1081px)').addEventListener('change', (e) => { if (e.matches) setOpen(false); });
  }

  // Copy BibTeX to the clipboard
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-copy]');
    if (!btn || !navigator.clipboard) return;
    const code = btn.parentElement.querySelector('code');
    navigator.clipboard.writeText(code.textContent.trim()).then(() => {
      btn.textContent = 'Copied';
      setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
    });
  });

  // Rotating words in the home page title (data/hero_words.toml). Pauses while the pointer is
  // on the title, while the title is scrolled out of view or the tab is hidden, and does not run
  // at all when the visitor prefers reduced motion.
  const rotator = document.querySelector('.hero-rotator');
  if (rotator && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const words = [...rotator.querySelectorAll('.hero-word')];
    const ms = Math.max(0.5, parseFloat(rotator.dataset.interval) || 2) * 1000;
    const title = rotator.closest('h1');
    let index = 0, timer = 0, inView = true, hovered = false;
    // Random order (data-random): a shuffled deck of all other words, so every word appears
    // once before any repeats and the same word never comes twice in a row.
    let deck = [];
    const nextIndex = () => {
      if (!rotator.hasAttribute('data-random')) return (index + 1) % words.length;
      if (!deck.length) {
        deck = words.map((_, k) => k).filter((k) => k !== index);
        for (let k = deck.length - 1; k > 0; k--) {
          const j = Math.floor(Math.random() * (k + 1));
          [deck[k], deck[j]] = [deck[j], deck[k]];
        }
      }
      return deck.pop();
    };
    const step = () => {
      const prev = words[index];
      index = nextIndex();
      const next = words[index];
      prev.classList.replace('is-current', 'is-leaving');
      next.classList.remove('is-leaving');
      next.classList.add('is-current');
      title.classList.toggle('has-s', next.hasAttribute('data-singular'));   // "meet" or "meets"
      setTimeout(() => { if (!prev.classList.contains('is-current')) prev.classList.remove('is-leaving'); }, 600);
    };
    const update = () => {
      clearInterval(timer);
      if (words.length > 1 && inView && !hovered && !document.hidden) timer = setInterval(step, ms);
    };
    title.addEventListener('mouseenter', () => { hovered = true; update(); });
    title.addEventListener('mouseleave', () => { hovered = false; update(); });
    document.addEventListener('visibilitychange', update);
    if ('IntersectionObserver' in window) {
      new IntersectionObserver((entries) => { inView = entries[0].isIntersecting; update(); }).observe(title);
    }
    update();
  }

  // YouTube videos (layouts/_partials/video.html): the player is loaded only after a click,
  // so nothing is sent to YouTube before. Ctrl/Cmd/Shift-click still opens the video on YouTube.
  document.addEventListener('click', (e) => {
    const link = e.target.closest('.video-load');
    const box = link && link.closest('[data-youtube]');
    if (!box || e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    const frame = document.createElement('iframe');
    frame.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(box.dataset.youtube)}?autoplay=1&rel=0`;
    frame.title = box.dataset.title || 'YouTube video';
    frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    frame.allowFullscreen = true;
    link.replaceWith(frame);
    frame.focus();
  });

  // Publication search and filters (state is kept in the URL, so filtered views can be shared)
  const form = document.querySelector('[data-pub-filter]');
  if (!form) return;
  const fold = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const items = [...document.querySelectorAll('.pub-years .pub')].map((el) => ({
    el, text: fold(el.dataset.search || ''), type: el.dataset.type, members: (el.dataset.members || '').split(' '),
  }));
  const years = [...document.querySelectorAll('.pub-years .pub-year')];
  const count = document.querySelector('[data-pub-count]');
  const empty = document.querySelector('[data-pub-empty]');
  const field = (name) => form.elements.namedItem(name);

  const apply = () => {
    const words = fold(field('q').value).split(/\s+/).filter(Boolean);
    const type = field('type').value;
    const member = field('member').value;
    let shown = 0;
    for (const it of items) {
      const ok = words.every((w) => it.text.includes(w))
        && (!type || it.type === type)
        && (!member || it.members.includes(member));
      it.el.hidden = !ok;
      if (ok) shown++;
    }
    for (const y of years) y.hidden = !y.querySelector('.pub:not([hidden])');
    if (count) count.textContent = shown;
    if (empty) empty.hidden = shown > 0;

    const params = new URLSearchParams();
    if (field('q').value.trim()) params.set('q', field('q').value.trim());
    if (type) params.set('type', type);
    if (member) params.set('member', member);
    const qs = params.toString();
    history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
  };

  const initial = new URLSearchParams(location.search);
  for (const name of ['q', 'type', 'member']) {
    if (initial.has(name)) field(name).value = initial.get(name);
  }
  form.addEventListener('input', apply);
  form.addEventListener('submit', (e) => e.preventDefault());
  apply();
})();
