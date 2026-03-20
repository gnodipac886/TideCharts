#!/usr/bin/env python3
import os
import re
import threading
import urllib.request
import urllib.parse
import json
import webbrowser

from flask import Flask, request, render_template_string, send_file, jsonify

import main as m

app = Flask(__name__)

SEARCH_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tide Chart Search</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    :root { --bar-height: 0px; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f5f5f5;
      height: 100vh;
      overflow: hidden;
      position: relative;
    }

    /* ── Search section ──────────────────────────────────────── */
    /* Starts vertically centered; transitions to top edge */
    #search-section {
      position: absolute;
      left: 0;
      right: 0;
      top: 50%;
      transform: translateY(-50%);
      display: flex;
      justify-content: center;
      padding: 0 24px;
      z-index: 10;
      transition:
        top      1.4s cubic-bezier(0.4, 0, 0.2, 1),
        transform 1.4s cubic-bezier(0.4, 0, 0.2, 1),
        padding  1.0s  ease,
        background 0.8s ease,
        box-shadow 0.8s ease;
    }

    body.has-results #search-section {
      top: 0;
      transform: translateY(0);
      background: white;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      padding: 10px 20px;
    }

    /* ── Card ── */
    .card {
      background: white;
      border-radius: 17px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.10);
      padding: 68px 56px 44px;
      width: 100%;
      max-width: 720px;
      text-align: center;
      transition:
        padding      1.0s ease,
        border-radius 1.0s ease,
        box-shadow   1.0s ease,
        max-width    1.1s ease,
        background   0.8s ease;
    }

    body.has-results .card {
      padding: 0;
      border-radius: 0;
      box-shadow: none;
      background: transparent;
      max-width: 100%;
      flex: 1;
      text-align: left;
    }

    /* ── Title / subtitle ── */
    .card-header {
      overflow: hidden;
      max-height: 140px;
      opacity: 1;
      margin-bottom: 28px;
      transition:
        max-height  1.0s ease,
        opacity     0.7s ease,
        margin      1.0s ease;
    }

    body.has-results .card-header {
      max-height: 0;
      opacity: 0;
      margin-bottom: 0;
    }

    h1 { font-size: 28px; font-weight: 700; color: #1a1a1a; margin-bottom: 8px; }
    p  { font-size: 15px; color: #666; }

    /* ── Year input (matches the main search bar style) ── */
    #year-input {
      width: 80px;
      padding: 12px 16px;
      font-size: 15px;
      font-family: inherit;
      color: #1a1a1a;
      border: 1.5px solid #ddd;
      border-radius: 8px;
      outline: none;
      text-align: center;
      transition: border-color 0.2s;
      -moz-appearance: textfield;
    }
    #year-input::-webkit-outer-spin-button,
    #year-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    #year-input:focus { border-color: #2d2d2d; }

    /* ── Autocomplete dropdown ── */
    .autocomplete-wrapper { position: relative; flex: 1; min-width: 0; }
    #autocomplete-list {
      position: absolute;
      top: calc(100% + 4px);
      left: 0; right: 0;
      background: white;
      border: 1.5px solid #ddd;
      border-radius: 8px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.10);
      z-index: 100;
      overflow: hidden;
      display: none;
    }
    #autocomplete-list.open { display: block; }
    .ac-item {
      padding: 10px 14px;
      font-size: 14px;
      color: #1a1a1a;
      cursor: pointer;
      border-bottom: 1px solid #f0f0f0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .ac-item:last-child { border-bottom: none; }
    .ac-item:hover, .ac-item.active { background: #f5f5f5; }

    /* ── Input row ── */
    .input-row {
      display: flex;
      gap: 10px;
      width: 100%;
    }

    input[type="text"] {
      width: 100%;
      padding: 12px 16px;
      font-size: 15px;
      border: 1.5px solid #ddd;
      border-radius: 8px;
      outline: none;
      transition: border-color 0.2s;
      min-width: 0;
    }
    input[type="text"]:focus { border-color: #2d2d2d; }

    button {
      padding: 12px 22px;
      background: #2d2d2d;
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
      white-space: nowrap;
    }
    button:hover  { background: #444; }
    button:disabled { background: #aaa; cursor: default; }

    /* ── Hint (below input, only on landing) ── */
    .hint {
      font-size: 13px;
      color: #aaa;
      margin-top: 10px;
      overflow: hidden;
      max-height: 30px;
      opacity: 1;
      transition:
        max-height 0.55s ease,
        opacity    0.7s ease,
        margin     0.55s ease;
    }
    body.has-results .hint {
      max-height: 0;
      opacity: 0;
      margin-top: 0;
    }

    /* ── Location info (fades in after transition) ── */
    #location-info {
      overflow: hidden;
      max-height: 0;
      opacity: 0;
      /* delay so it appears only after bar has settled */
      transition:
        max-height 0.6s ease 1.2s,
        opacity    0.6s ease 1.2s,
        margin     0.6s ease 1.2s;
      margin-top: 0;
    }
    body.has-results #location-info {
      max-height: 50px;
      opacity: 1;
      margin-top: 5px;
    }
    #location-address {
      font-size: 12.5px;
      color: #555;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    #location-station {
      font-size: 11.5px;
      color: #999;
      margin-top: 1px;
    }

    /* ── Status / error (only on landing) ── */
    .status {
      font-size: 13px;
      color: #888;
      margin-top: 8px;
      min-height: 18px;
    }
    body.has-results .status { display: none; }
    .error { color: #c0392b; }

    /* ── Chart section ── */
    #chart-section {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      top: var(--bar-height);
      opacity: 0;
      pointer-events: none;
    }
    #chart-section.visible {
      opacity: 1;
      pointer-events: auto;
      transition: opacity 0.35s ease;
    }

    #chart-frame {
      width: 100%;
      height: 100%;
      border: none;
      display: block;
    }
  </style>
</head>
<body>
  <div id="search-section">
    <div class="card">
      <div class="card-header">
        <h1>🌊 Tide Chart</h1>
        <p>Search any coastal location to see low tide predictions for the year below.</p>
      </div>
      <div class="input-row">
        <div class="autocomplete-wrapper">
          <input type="text" id="query"
                 placeholder="e.g. Half Moon Bay, CA"
                 autocomplete="off">
          <div id="autocomplete-list"></div>
        </div>
        <input type="number" id="year-input" value="{{ year }}" min="2000" max="2100">
        <button id="btn" onclick="doSearch()">Search</button>
      </div>
      <div class="hint">Finds the nearest NOAA tide prediction station</div>
      <div id="location-info">
        <div id="location-address"></div>
        <div id="location-station"></div>
      </div>
      <div class="status" id="status"></div>
    </div>
  </div>

  <div id="chart-section">
    <iframe id="chart-frame"></iframe>
  </div>

  <script>
    const input      = document.getElementById('query');
    const yearInput  = document.getElementById('year-input');
    const btn        = document.getElementById('btn');
    const status     = document.getElementById('status');
    const frame      = document.getElementById('chart-frame');
    const addrEl     = document.getElementById('location-address');
    const stationEl  = document.getElementById('location-station');
    const searchSec  = document.getElementById('search-section');
    const chartSec   = document.getElementById('chart-section');
    const acList     = document.getElementById('autocomplete-list');

    // ── Autocomplete ──────────────────────────────────────────────
    let acDebounce = null;
    let acActiveIdx = -1;

    input.addEventListener('input', () => {
      clearTimeout(acDebounce);
      const q = input.value.trim();
      if (q.length < 3) { closeAc(); return; }
      acDebounce = setTimeout(() => fetchSuggestions(q), 300);
    });

    input.addEventListener('keydown', e => {
      const items = acList.querySelectorAll('.ac-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        acActiveIdx = Math.min(acActiveIdx + 1, items.length - 1);
        highlightAc(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        acActiveIdx = Math.max(acActiveIdx - 1, -1);
        highlightAc(items);
      } else if (e.key === 'Enter') {
        if (acActiveIdx >= 0 && items[acActiveIdx]) {
          items[acActiveIdx].click();
        } else {
          closeAc();
          doSearch();
        }
      } else if (e.key === 'Escape') {
        closeAc();
      }
    });

    document.addEventListener('click', e => {
      if (!e.target.closest('.autocomplete-wrapper')) closeAc();
    });

    async function fetchSuggestions(q) {
      try {
        const resp = await fetch('/autocomplete?q=' + encodeURIComponent(q));
        const suggestions = await resp.json();
        renderAc(suggestions);
      } catch (_) { closeAc(); }
    }

    function renderAc(suggestions) {
      acList.innerHTML = '';
      acActiveIdx = -1;
      if (!suggestions.length) { closeAc(); return; }
      suggestions.forEach(s => {
        const div = document.createElement('div');
        div.className = 'ac-item';
        div.textContent = s;
        div.addEventListener('mousedown', e => {
          e.preventDefault(); // keep focus on input
          input.value = s;
          closeAc();
          doSearch();
        });
        acList.appendChild(div);
      });
      acList.classList.add('open');
    }

    function highlightAc(items) {
      items.forEach((el, i) => el.classList.toggle('active', i === acActiveIdx));
    }

    function closeAc() {
      acList.classList.remove('open');
      acList.innerHTML = '';
      acActiveIdx = -1;
    }

    // ── Search ────────────────────────────────────────────────────
    yearInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

    async function doSearch() {
      const query = input.value.trim();
      if (!query) return;

      closeAc();
      btn.disabled = true;
      btn.textContent = 'Generating\u2026';
      status.textContent = 'Geocoding location and fetching NOAA data\u2026';
      status.className = 'status';

      try {
        const fd = new FormData();
        fd.append('query', query);
        fd.append('year', yearInput.value);
        const resp = await fetch('/search', { method: 'POST', body: fd });
        const data = await resp.json();

        if (!resp.ok || data.error) {
          status.textContent = data.error || 'Unknown error';
          status.className = 'status error';
          return;
        }

        // Populate location info before animating so it's ready
        addrEl.textContent   = '📍 ' + data.address;
        stationEl.textContent = 'Nearest station: ' + data.station;

        // Point iframe at chart route (include year so the right file is served)
        frame.src = '/chart/' + encodeURIComponent(data.key) + '?year=' + data.year;

        // Step 1: trigger the slide-to-top animation
        document.body.classList.add('has-results');

        // Step 2: once the bar has settled, measure its final height,
        //         set the chart top edge, then fade the chart in
        setTimeout(() => {
          const barH = searchSec.getBoundingClientRect().height;
          document.documentElement.style.setProperty('--bar-height', barH + 'px');
          chartSec.classList.add('visible');
        }, 1350); // slightly after the 1.4s transition

      } catch (err) {
        status.textContent = 'Network error: ' + err.message;
        status.className = 'status error';
      } finally {
        btn.disabled = false;
        btn.textContent = 'Search';
      }
    }
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(SEARCH_PAGE, year=m.year)

@app.route('/autocomplete')
def autocomplete():
    q = request.args.get('q', '').strip()
    if len(q) < 3:
        return jsonify([])
    try:
        params = urllib.parse.urlencode({'q': q, 'format': 'json', 'limit': 6, 'addressdetails': 0})
        req = urllib.request.Request(
            f'https://nominatim.openstreetmap.org/search?{params}',
            headers={'User-Agent': 'tidepool2/1.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read())
        suggestions = [r['display_name'] for r in results]
        return jsonify(suggestions)
    except Exception:
        return jsonify([])


@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query', '').strip()
    if not query:
        return jsonify(error='No query provided.'), 400
    year_str = request.form.get('year', str(m.year)).strip()
    try:
        year = int(year_str)
        if not (2000 <= year <= 2100):
            raise ValueError()
    except ValueError:
        return jsonify(error='Invalid year (must be 2000–2100).'), 400
    try:
        m.year = year
        result = m.search_and_plot(query)
        return jsonify(
            key=result['key'],
            address=result['address'],
            station=result['station'],
            year=year,
        )
    except ValueError as e:
        return jsonify(error=str(e)), 404
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/chart/<key>')
def chart(key):
    key = re.sub(r'[^a-zA-Z0-9]', '', key)
    year_str = request.args.get('year', str(m.year))
    try:
        year = int(year_str)
    except ValueError:
        year = m.year
    path = os.path.join(os.getcwd(), f"tideplot_{year}_{key.lower()}.html")
    if not os.path.exists(path):
        return 'Chart not found.', 404
    return send_file(path)

if __name__ == '__main__':
    port = 8080
    threading.Timer(1.2, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    print(f"Starting tide chart server at http://localhost:{port}")
    app.run(port=port, debug=False)
