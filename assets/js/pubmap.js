/*
  Publication map on the home page (layouts/_partials/pubmap.html, data from
  scripts/update_publication_map.py). Places the publications as topic clusters with a small,
  deterministic force simulation (no library), draws them as SVG, and shows a card with the
  abstract and the authors on hover, keyboard focus or tap. The publications can be grouped in
  several ways (methods, applications); the switch above the map moves the circles to their
  clusters in the other grouping. Re-lays out when the width changes.
*/
(function () {
  'use strict';
  var root = document.querySelector('.pubmap');
  if (!root) return;
  var canvas = root.querySelector('[data-pubmap]');
  var data;
  try { data = JSON.parse(root.querySelector('.pubmap-data').textContent); } catch (e) { return; }
  if (!data || !data.nodes || !data.nodes.length || !data.groupings || !data.groupings.length) return;

  var SVGNS = 'http://www.w3.org/2000/svg';
  var GRAY = '#8a94a6';
  var reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var groupings = data.groupings;
  var topicsOf = new Map(groupings.map(function (g) {
    return [g.key, new Map(g.topics.map(function (t) { return [t.key, t]; }))];
  }));
  var current = groupings[0].key;
  var nodes = data.nodes.map(function (n) { return Object.assign({ pos: {} }, n); });
  var byId = new Map(nodes.map(function (n) { return [n.id, n]; }));
  var links = data.links.map(function (l) { return { s: byId.get(l.s), t: byId.get(l.t), k: l.k }; })
    .filter(function (l) { return l.s && l.t; });
  var near = new Map(nodes.map(function (n) { return [n, new Set()]; }));
  links.forEach(function (l) { near.get(l.s).add(l.t); near.get(l.t).add(l.s); });
  var maxCites = Math.max.apply(null, [1].concat(nodes.map(function (n) { return n.cites || 0; })));
  var labels = [];
  var nodeOfEl = new WeakMap();

  function el(name, attrs) {
    var e = document.createElementNS(SVGNS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function grouping(key) { return groupings.filter(function (g) { return g.key === (key || current); })[0]; }
  function topicOf(n, key) { return (n.topics || {})[key || current]; }
  function topic(n, key) { return topicsOf.get(key || current).get(topicOf(n, key)); }
  function color(n) { var t = topic(n); return t ? t.color : GRAY; }
  // A gently curved line between two publications
  function curve(l) {
    return [(l.s.x + l.t.x) / 2 - (l.t.y - l.s.y) * 0.12, (l.s.y + l.t.y) / 2 + (l.t.x - l.s.x) * 0.12];
  }
  function linkPath(l) {
    var q = curve(l);
    return 'M' + l.s.x + ',' + l.s.y + ' Q' + q[0] + ',' + q[1] + ' ' + l.t.x + ',' + l.t.y;
  }

  canvas.textContent = '';
  var svg = el('svg', { class: 'pubmap-svg', role: 'group', 'aria-label': 'Map of our publications' });
  var gHalos = el('g', { class: 'pm-halos', 'aria-hidden': 'true' });
  var gLinks = el('g', { class: 'pm-links', 'aria-hidden': 'true' });
  var gNodes = el('g', { class: 'pm-nodes' });
  var gLabels = el('g', { class: 'pm-labels', 'aria-hidden': 'true' });
  svg.append(gHalos, gLinks, gNodes, gLabels);
  var card = document.createElement('div');
  card.className = 'pubmap-card';
  card.hidden = true;
  canvas.append(svg, card);

  // ------------------------------------------------------------------ layout

  function setRadii(W, H) {
    var unit = Math.sqrt(W * H / Math.max(nodes.length, 12));   // circle sizes scale with the space per publication
    var rMin = clamp(unit * 0.065, 5, 9), rMax = clamp(unit * 0.19, 11, 24);
    nodes.forEach(function (n) { n.r = rMin + (rMax - rMin) * Math.sqrt((n.cites || 0) / maxCites); });
    return [rMin, rMax];
  }

  // Positions of all publications in grouping g, stored in n.pos[g.key]
  function layout(W, H, g, rMin, rMax) {
    var small = W < 640;
    var key = g.key;
    var groups = new Map();
    nodes.forEach(function (n) {
      var k = topicOf(n, key);
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(n);
    });
    function clusterRadius(k) {
      var area = (groups.get(k) || []).reduce(function (a, n) { return a + Math.pow(n.r + 7, 2); }, 0);
      return Math.sqrt(area * 1.5);
    }
    // Cluster anchors: the best-connected topic in the middle, the others on an ellipse around it.
    var pad = small ? 20 : 30;
    var center = g.layout && g.layout.center;
    var ring = ((g.layout && g.layout.ring) || g.topics.map(function (t) { return t.key; }))
      .filter(function (k) { return groups.has(k) && k !== center; });
    groups.forEach(function (_, k) { if (k !== center && ring.indexOf(k) < 0) ring.push(k); });
    var maxR = Math.max.apply(null, [0].concat(ring.map(clusterRadius)));
    var rx = W / 2 - pad - maxR, ry = H / 2 - pad - maxR - 8;
    // Rotate the ring so that the clusters are as far apart as possible for this aspect ratio
    function anchorsAt(start) {
      var m = new Map();
      if (center && groups.has(center)) m.set(center, { x: W / 2, y: H / 2, r: clusterRadius(center) });
      ring.forEach(function (k, i) {
        var a = start + 2 * Math.PI * i / ring.length;
        m.set(k, { x: W / 2 + rx * Math.cos(a), y: H / 2 + ry * Math.sin(a), r: clusterRadius(k) });
      });
      return m;
    }
    function spacing(m) {
      var list = Array.from(m.values()), worst = Infinity;
      for (var i = 0; i < list.length; i++) {
        for (var j = i + 1; j < list.length; j++) {
          worst = Math.min(worst, Math.hypot(list[i].x - list[j].x, list[i].y - list[j].y) - list[i].r - list[j].r);
        }
      }
      return worst;
    }
    var anchors = anchorsAt(-Math.PI / 2), bestSpacing = spacing(anchors);
    for (var s = 1; s < 36; s++) {
      var cand = anchorsAt(-Math.PI / 2 + 2 * Math.PI / Math.max(ring.length, 1) * s / 36);
      var sp = spacing(cand);
      if (sp > bestSpacing + 0.5) { anchors = cand; bestSpacing = sp; }
    }

    // Deterministic start: a sunflower spiral around each anchor, most cited in the middle.
    var golden = Math.PI * (3 - Math.sqrt(5));
    groups.forEach(function (list, k) {
      var A = anchors.get(k);
      list.slice().sort(function (a, b) { return b.r - a.r || (a.id < b.id ? -1 : 1); }).forEach(function (n, i) {
        var d = (rMin + rMax) * 0.85 * Math.sqrt(i + 0.3);
        n.x = A.x + d * Math.cos(i * golden);
        n.y = A.y + d * Math.sin(i * golden);
        n.vx = n.vy = 0;
      });
    });

    var steps = 320;
    for (var it = 0; it < steps; it++) {
      var alpha = 1 - it / steps;
      // Pull towards the cluster's anchor and, to keep clusters round, towards their own center
      var centers = new Map();
      groups.forEach(function (list, k) {
        var cx = 0, cy = 0;
        list.forEach(function (n) { cx += n.x / list.length; cy += n.y / list.length; });
        centers.set(k, { x: cx, y: cy });
      });
      nodes.forEach(function (n) {
        var A = anchors.get(topicOf(n, key)), C = centers.get(topicOf(n, key)), f = 0.014 * (0.35 + 0.65 * alpha);
        n.vx += (A.x - n.x) * f + (C.x - n.x) * 0.03;
        n.vy += (A.y - n.y) * f + (C.y - n.y) * 0.03;
      });
      links.forEach(function (l) {
        var a = l.s, b = l.t, dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1;
        var same = topicOf(a, key) === topicOf(b, key);
        var f = (d - (a.r + b.r + (same ? 16 : 40))) / d * (same ? 0.02 : 0.0015) * alpha;
        a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
      });
      nodes.forEach(function (n) { n.vx *= 0.55; n.vy *= 0.55; n.x += n.vx; n.y += n.vy; });
      for (var i = 0; i < nodes.length; i++) {
        for (var j = i + 1; j < nodes.length; j++) {
          var a = nodes[i], b = nodes[j];
          var dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.01;
          var min = a.r + b.r + (topicOf(a, key) === topicOf(b, key) ? 6 : (small ? 22 : 36));
          if (d < min) {
            var push = (min - d) / d / 2;
            a.x -= dx * push; a.y -= dy * push; b.x += dx * push; b.y += dy * push;
          }
        }
      }
      // Keep the topic areas (circles around each cluster) from overlapping
      var areas = [];
      groups.forEach(function (list) {
        var cx = 0, cy = 0;
        list.forEach(function (n) { cx += n.x / list.length; cy += n.y / list.length; });
        var r = Math.max.apply(null, list.map(function (n) { return Math.hypot(n.x - cx, n.y - cy) + n.r; })) + 12;
        areas.push({ list: list, x: cx, y: cy, r: r });
      });
      for (var p = 0; p < areas.length; p++) {
        for (var q = p + 1; q < areas.length; q++) {
          var A1 = areas[p], A2 = areas[q];
          var ax = A2.x - A1.x, ay = A2.y - A1.y, ad = Math.hypot(ax, ay) || 0.01;
          var gap = A1.r + A2.r + 6 - ad;
          if (gap > 0) {
            var sh = gap / ad * 0.25;
            A1.list.forEach(function (n) { n.x -= ax * sh; n.y -= ay * sh; });
            A2.list.forEach(function (n) { n.x += ax * sh; n.y += ay * sh; });
          }
        }
      }
      nodes.forEach(function (n) {
        n.x = clamp(n.x, 6 + n.r, W - 6 - n.r);
        n.y = clamp(n.y, pad + n.r, H - 6 - n.r);
      });
    }
    nodes.forEach(function (n) { n.pos[key] = { x: n.x, y: n.y }; });
  }

  // Topic labels next to their cluster: above, below, right or left, wherever they cover least.
  function placeLabels(W, H) {
    var placed = [];
    var linkPoints = [];   // points along the lines, which labels should not cover either
    links.forEach(function (l) {
      var q = curve(l);
      for (var s = 1; s < 12; s++) {
        var u = s / 12;
        linkPoints.push([(1 - u) * (1 - u) * l.s.x + 2 * u * (1 - u) * q[0] + u * u * l.t.x,
                         (1 - u) * (1 - u) * l.s.y + 2 * u * (1 - u) * q[1] + u * u * l.t.y]);
      }
    });
    labels.forEach(function (lb) {
      var list = nodes.filter(function (n) { return topicOf(n) === lb.key; });
      var x0 = Math.min.apply(null, list.map(function (n) { return n.x - n.r; }));
      var x1 = Math.max.apply(null, list.map(function (n) { return n.x + n.r; }));
      var y0 = Math.min.apply(null, list.map(function (n) { return n.y - n.r; }));
      var y1 = Math.max.apply(null, list.map(function (n) { return n.y + n.r; }));
      var cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
      var w = lb.text.getComputedTextLength(), h = lb.size;
      var options = [
        { x: cx - w / 2, y: y0 - 8 - h, cost: 0 },
        { x: cx - w / 2, y: y1 + 8, cost: 1 },
        { x: x1 + 8, y: cy - h / 2, cost: 2 },
        { x: x0 - 8 - w, y: cy - h / 2, cost: 2 }
      ];
      var best = null;
      options.forEach(function (o) {
        var x = clamp(o.x, 4, W - w - 4), y = clamp(o.y, 2, H - h - 2);
        var cost = o.cost + (Math.abs(x - o.x) + Math.abs(y - o.y)) * 0.5;
        nodes.forEach(function (n) {
          var ox = Math.max(0, Math.min(x + w, n.x + n.r + 3) - Math.max(x, n.x - n.r - 3));
          var oy = Math.max(0, Math.min(y + h, n.y + n.r + 3) - Math.max(y, n.y - n.r - 3));
          cost += ox * oy * 0.5;
        });
        linkPoints.forEach(function (p) {
          if (p[0] > x - 2 && p[0] < x + w + 2 && p[1] > y - 2 && p[1] < y + h + 2) cost += 12;
        });
        placed.forEach(function (p) {
          var ox = Math.max(0, Math.min(x + w, p.x + p.w + 6) - Math.max(x, p.x - 6));
          var oy = Math.max(0, Math.min(y + h, p.y + p.h + 4) - Math.max(y, p.y - 4));
          cost += ox * oy;
        });
        if (!best || cost < best.cost) best = { x: x, y: y, w: w, h: h, cost: cost };
      });
      placed.push(best);
      lb.text.setAttribute('x', best.x);
      lb.text.setAttribute('y', best.y + h * 0.8);
    });
  }

  // ------------------------------------------------------------------ drawing

  var W = 0, H = 0, morph = 0;

  function render() {
    W = canvas.clientWidth; H = canvas.clientHeight;
    if (!W || !H) return;
    cancelAnimationFrame(morph);
    svg.classList.remove('is-morphing');
    hide();
    var r = setRadii(W, H);
    groupings.forEach(function (g) { layout(W, H, g, r[0], r[1]); });
    nodes.forEach(function (n) { n.x = n.pos[current].x; n.y = n.pos[current].y; });
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

    gLinks.textContent = '';
    links.forEach(function (l) {
      l.el = el('path', { class: 'pm-link pm-' + l.k, d: linkPath(l) });
      gLinks.append(l.el);
    });
    gNodes.textContent = '';
    nodes.slice().sort(function (a, b) { return b.r - a.r; }).forEach(function (n) {
      var g = el('g', { class: 'pm-node', tabindex: '0', role: 'button', transform: 'translate(' + n.x + ',' + n.y + ')' });
      g.style.setProperty('--d', (Math.hypot(n.x - W / 2, n.y - H / 2) / Math.hypot(W, H) * 0.9).toFixed(2) + 's');
      g.append(el('circle', { class: 'pm-hit', r: Math.max(n.r + 5, 13) }), el('circle', { class: 'pm-dot', r: n.r }));
      nodeOfEl.set(g, n);
      n.el = g;
      gNodes.append(g);
    });
    paintNodes();
    drawClusters();
  }

  // Colors and accessible names of the circles for the current grouping
  function paintNodes() {
    nodes.forEach(function (n) {
      var t = topic(n);
      n.el.style.setProperty('--c', color(n));
      n.el.setAttribute('aria-label', n.title + ' (' + n.year + (t ? ', ' + t.name : '') + ')');
    });
  }

  // Topic areas and labels of the current grouping
  function drawClusters() {
    gHalos.textContent = '';
    gLabels.textContent = '';
    var g = grouping();
    g.topics.forEach(function (t) {
      var list = nodes.filter(function (n) { return topicOf(n) === t.key; });
      if (!list.length) return;
      var cx = list.reduce(function (a, n) { return a + n.x; }, 0) / list.length;
      var cy = list.reduce(function (a, n) { return a + n.y; }, 0) / list.length;
      var r = Math.max.apply(null, list.map(function (n) { return Math.hypot(n.x - cx, n.y - cy) + n.r; })) + 12;
      var halo = el('circle', { class: 'pm-halo', cx: cx, cy: cy, r: r });
      halo.style.setProperty('--c', t.color);
      gHalos.append(halo);
    });
    var size = W < 640 ? 11.5 : 13;
    labels = g.topics.filter(function (t) { return nodes.some(function (n) { return topicOf(n) === t.key; }); })
      .map(function (t) {
        var text = el('text', { class: 'pm-label', 'font-size': size });
        text.textContent = t.name;
        gLabels.append(text);
        return { key: t.key, text: text, size: size };
      });
    placeLabels(W, H);
    applyHighlight();
  }

  // Switch to another grouping: the circles move to their new clusters and change color.
  function switchTo(key) {
    if (key === current || !grouping(key)) return;
    hide();
    hoverTopic = stickyTopic = null;
    current = key;
    syncControls();
    paintNodes();
    svg.classList.add('is-morphing');
    cancelAnimationFrame(morph);
    var from = nodes.map(function (n) { return { x: n.x, y: n.y }; });
    var duration = reduceMotion ? 0 : 950;
    var lag = nodes.map(function (n, i) { return reduceMotion ? 0 : (i * 7 % 11) / 10 * 220; });  // slight stagger
    var t0 = performance.now();
    function frame(now) {
      var done = true;
      nodes.forEach(function (n, i) {
        var u = duration ? clamp((now - t0 - lag[i]) / duration, 0, 1) : 1;
        if (u < 1) done = false;
        var e = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;   // ease in-out
        n.x = from[i].x + (n.pos[key].x - from[i].x) * e;
        n.y = from[i].y + (n.pos[key].y - from[i].y) * e;
        n.el.setAttribute('transform', 'translate(' + n.x + ',' + n.y + ')');
      });
      links.forEach(function (l) { l.el.setAttribute('d', linkPath(l)); });
      if (!done) { morph = requestAnimationFrame(frame); return; }
      morph = 0;
      drawClusters();
      svg.classList.remove('is-morphing');
    }
    morph = requestAnimationFrame(frame);
  }

  // ------------------------------------------------------------------ card

  function add(parent, tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    parent.append(e);
    return e;
  }

  function fillCard(n) {
    card.textContent = '';
    var t = topic(n);
    var close = add(card, 'button', 'pm-close');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close');
    close.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
    close.addEventListener('click', function () { var a = active; hide(); if (a) a.el.focus(); });

    var meta = add(card, 'p', 'pm-meta');
    var key = add(meta, 'span', 'pm-key');
    key.style.setProperty('--c', color(n));
    add(meta, 'span', null, [t ? t.name : '', n.type, n.year].filter(Boolean).join(' · '));

    var h = add(card, 'h3', 'pm-title');
    if (n.url) { var a = add(h, 'a', null, n.title); a.href = n.url; } else h.textContent = n.title;

    var authors = add(card, 'p', 'pm-authors');
    (n.authors || []).forEach(function (au, i) {
      if (i) authors.append(', ');
      if (au.href) {
        var a = add(authors, 'a', au.member ? 'pm-member' : null, au.name);
        a.href = au.href;
        if (!au.member) a.title = 'ORCID profile';
      } else authors.append(au.name);
    });
    if (n.more) authors.append(', et al.');

    if (n.venue) add(card, 'p', 'pm-venue', n.venue);
    add(card, 'p', 'pm-abstract' + (n.abstract ? '' : ' is-empty'), n.abstract || 'No abstract available.');

    var foot = add(card, 'p', 'pm-foot');
    add(foot, 'span', null, n.cites ? 'Cited ' + n.cites + (n.cites === 1 ? ' time' : ' times') : '');
    if (n.url) {
      var open = add(foot, 'a', null, 'Open publication');
      open.href = n.url;
      open.insertAdjacentHTML('beforeend', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg>');
    }
  }

  function placeCard(n) {
    card.hidden = false;
    var sheet = W < 640;
    card.classList.toggle('is-sheet', sheet);
    if (sheet) {
      card.classList.toggle('at-top', n.y > H / 2);
      card.style.left = card.style.top = '';
      return;
    }
    var cw = card.offsetWidth, ch = card.offsetHeight, gap = n.r + 14;
    var x = n.x + gap;
    if (x + cw > W - 8) x = n.x - gap - cw;
    card.style.left = clamp(x, 8, W - cw - 8) + 'px';
    card.style.top = clamp(n.y - ch / 2, 8, H - ch - 8) + 'px';
  }

  // ------------------------------------------------------------------ interaction

  var active = null, pinned = false, hideTimer = 0, hoverTopic = null, stickyTopic = null;

  function applyHighlight() {
    var t = hoverTopic || stickyTopic;
    svg.classList.toggle('has-focus', !!active);
    svg.classList.toggle('has-topic', !active && !!t);
    nodes.forEach(function (n) {
      if (!n.el) return;
      n.el.classList.toggle('is-active', n === active);
      n.el.classList.toggle('is-near', !!active && near.get(active).has(n));
      n.el.classList.toggle('is-topic', !active && topicOf(n) === t);
    });
    links.forEach(function (l) {
      if (!l.el) return;
      l.el.classList.toggle('is-on', active ? (l.s === active || l.t === active)
        : !!t && topicOf(l.s) === t && topicOf(l.t) === t);
    });
    labels.forEach(function (lb) { lb.text.classList.toggle('is-topic', !active && lb.key === t); });
  }

  function show(n, pin) {
    if (morph) return;
    clearTimeout(hideTimer);
    if (active !== n || card.hidden) fillCard(n);
    pinned = !!pin || (pinned && active === n);
    active = n;
    card.classList.toggle('is-pinned', pinned);
    applyHighlight();
    placeCard(n);
  }
  function hide() {
    clearTimeout(hideTimer);
    card.hidden = true;
    active = null;
    pinned = false;
    applyHighlight();
  }
  function hideSoon() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, 300);
  }
  function nodeOf(target) {
    var g = target && target.closest ? target.closest('.pm-node') : null;
    return g ? nodeOfEl.get(g) : null;
  }

  svg.addEventListener('pointerover', function (e) {
    var n = nodeOf(e.target);
    if (!n || e.pointerType === 'touch' || (pinned && active !== n)) return;
    show(n, false);
  });
  svg.addEventListener('pointerout', function (e) {
    var n = nodeOf(e.target);
    if (!n || e.pointerType === 'touch' || pinned || nodeOf(e.relatedTarget) === n) return;
    hideSoon();
  });
  card.addEventListener('pointerenter', function () { clearTimeout(hideTimer); });
  card.addEventListener('pointerleave', function (e) { if (!pinned && e.pointerType !== 'touch') hideSoon(); });
  svg.addEventListener('click', function (e) {
    var n = nodeOf(e.target);
    if (n) show(n, true); else hide();
  });
  svg.addEventListener('focusin', function (e) {
    var n = nodeOf(e.target);
    if (n && active !== n) show(n, false);
  });
  svg.addEventListener('focusout', function (e) {
    if (!pinned && !card.contains(e.relatedTarget) && !nodeOf(e.relatedTarget)) hideSoon();
  });
  card.addEventListener('focusout', function (e) {
    if (!card.contains(e.relatedTarget) && !nodeOf(e.relatedTarget)) hideSoon();
  });
  svg.addEventListener('keydown', function (e) {
    var n = nodeOf(e.target);
    if (n && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      show(n, true);
      var a = card.querySelector('.pm-title a');
      if (a) a.focus();
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && active) { var a = active; hide(); a.el.focus(); }
  });
  document.addEventListener('click', function (e) { if (active && !root.contains(e.target)) hide(); });

  // Legend (one per grouping) and the grouping switch
  var legends = root.querySelectorAll('.pubmap-legend');
  var switchEl = root.querySelector('.pubmap-switch');
  var switchButtons = root.querySelectorAll('.pubmap-switch button');
  function syncControls() {
    legends.forEach(function (ul) { ul.hidden = ul.getAttribute('data-grouping') !== current; });
    root.querySelectorAll('.pubmap-legend button').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
    switchButtons.forEach(function (b, i) {
      var on = b.getAttribute('data-grouping') === current;
      b.setAttribute('aria-pressed', String(on));
      if (on && switchEl) switchEl.style.setProperty('--i', i);
    });
  }
  switchButtons.forEach(function (b) {
    b.addEventListener('click', function () { switchTo(b.getAttribute('data-grouping')); });
  });
  root.querySelectorAll('.pubmap-legend button').forEach(function (b) {
    var key = b.getAttribute('data-topic');
    function enter() { if (!morph) { hoverTopic = key; applyHighlight(); } }
    function leave() { hoverTopic = null; applyHighlight(); }
    b.addEventListener('mouseenter', enter);
    b.addEventListener('mouseleave', leave);
    b.addEventListener('focus', enter);
    b.addEventListener('blur', leave);
    b.addEventListener('click', function () {
      stickyTopic = stickyTopic === key ? null : key;
      b.closest('.pubmap-legend').querySelectorAll('button').forEach(function (o) {
        o.setAttribute('aria-pressed', String(o.getAttribute('data-topic') === stickyTopic));
      });
      if (active) hide(); else applyHighlight();
    });
  });

  // ------------------------------------------------------------------ start

  render();
  syncControls();
  root.classList.add('is-ready');
  // Short entrance animation when the map first scrolls into view (not with reduced motion)
  if ('IntersectionObserver' in window && !reduceMotion) {
    svg.classList.add('is-pending');
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) {
        svg.classList.remove('is-pending');
        svg.classList.add('is-entering');
        setTimeout(function () { svg.classList.remove('is-entering'); }, 2000);
        io.disconnect();
      }
    }, { threshold: 0.25 });
    io.observe(canvas);
  }
  if ('ResizeObserver' in window) {
    var timer = 0;
    new ResizeObserver(function () {
      if (Math.abs(canvas.clientWidth - W) < 2) return;
      clearTimeout(timer);
      timer = setTimeout(render, 120);
    }).observe(canvas);
  }
})();
