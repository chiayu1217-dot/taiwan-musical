// ===== State =====
const state = {
  year: new Date().getFullYear(),
  month: new Date().getMonth(),
  allShows: [],
  selectedDate: null,
  filterRegion: '',
  filterSearch: '',
};

// ===== Data loading =====
async function loadShows() {
  try {
    const res = await fetch('data/shows.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.allShows = await res.json();
  } catch (err) {
    console.error('Failed to load shows:', err);
  }
  renderCalendar();
}

// ===== Pure helpers =====
function groupByDate(shows) {
  const map = {};
  for (const show of shows) {
    if (!map[show.date]) map[show.date] = [];
    map[show.date].push(show);
  }
  return map;
}

function applyFilters(shows) {
  return shows.filter(show => {
    if (state.filterRegion && show.region !== state.filterRegion) return false;
    if (state.filterSearch && !show.title.toLowerCase().includes(state.filterSearch.toLowerCase())) return false;
    return true;
  });
}

function dotClass(region) {
  if (region === '北部') return 'dot-north';
  if (region === '中部') return 'dot-central';
  if (region === '南部') return 'dot-south';
  if (region === '東部') return 'dot-east';
  if (region === '離島') return 'dot-island';
  return 'dot-other';
}

function pad(n) { return String(n).padStart(2, '0'); }

function toDateStr(year, month, day) {
  return `${year}-${pad(month + 1)}-${pad(day)}`;
}

function shortVenue(venue) {
  const cut = venue.split(/[．・\n]/)[0].trim();
  return cut.length > 18 ? cut.slice(0, 18) + '…' : cut;
}

function mergeSessionsForDay(shows) {
  const groups = new Map();
  for (const show of shows) {
    const key = `${show.title}||${show.venue}`;
    if (!groups.has(key)) groups.set(key, { ...show, times: [] });
    groups.get(key).times.push(show.time);
  }
  return [...groups.values()];
}

function renderDots(dayEl, shows, merged) {
  const dotsRow = document.createElement('div');
  dotsRow.className = 'dots-row';

  const dotsEl = document.createElement('div');
  dotsEl.className = 'dots';
  [...new Set(shows.map(s => s.region))].forEach(region => {
    const dot = document.createElement('span');
    dot.className = `dot ${dotClass(region)}`;
    dotsEl.appendChild(dot);
  });
  dotsRow.appendChild(dotsEl);

  if (merged.length > 1) {
    const badge = document.createElement('span');
    badge.className = 'show-badge';
    badge.textContent = merged.length;
    dotsRow.appendChild(badge);
  }
  dayEl.appendChild(dotsRow);
}

// ===== Calendar rendering =====
function renderCalendar() {
  const { year, month } = state;
  const filtered = applyFilters(state.allShows);
  const grouped = groupByDate(filtered);

  document.getElementById('month-label').textContent = `${year}年${month + 1}月`;

  const firstDay = new Date(year, month, 1).getDay();
  const startOffset = (firstDay + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const prevMonthDays = new Date(year, month, 0).getDate();

  const cells = [];
  for (let i = startOffset - 1; i >= 0; i--) cells.push({ day: prevMonthDays - i, current: false });
  for (let d = 1; d <= daysInMonth; d++) cells.push({ day: d, current: true });
  const rem = cells.length % 7;
  if (rem > 0) for (let d = 1; d <= 7 - rem; d++) cells.push({ day: d, current: false });

  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  const today = new Date();
  const todayStr = toDateStr(today.getFullYear(), today.getMonth(), today.getDate());

  const weeksEl = document.getElementById('weeks');
  weeksEl.innerHTML = '';

  let hasAnyShow = false;

  weeks.forEach((week, wi) => {
    const weekRow = document.createElement('div');
    weekRow.className = 'week-row';

    const weekDays = document.createElement('div');
    weekDays.className = 'week-days';

    week.forEach(cell => {
      const dateStr = cell.current ? toDateStr(year, month, cell.day) : null;
      const shows = dateStr ? (grouped[dateStr] || []) : [];
      if (shows.length > 0) hasAnyShow = true;

      const dayEl = document.createElement('div');
      dayEl.className = 'day-cell';
      if (!cell.current) dayEl.classList.add('other-month');
      if (dateStr === todayStr) dayEl.classList.add('today');
      if (shows.length > 0) dayEl.classList.add('has-shows');
      if (dateStr === state.selectedDate) dayEl.classList.add('selected');
      if (dateStr) dayEl.dataset.date = dateStr;

      const numEl = document.createElement('span');
      numEl.className = 'day-num';
      numEl.textContent = cell.day;
      dayEl.appendChild(numEl);

      if (shows.length > 0) {
        const merged = mergeSessionsForDay(shows);
        const firstImage = merged.find(s => s.image_url)?.image_url;

        if (firstImage) {
          dayEl.classList.add('has-poster');
          const wrap = document.createElement('div');
          wrap.className = 'cal-poster-wrap';

          const img = document.createElement('img');
          img.className = 'cal-poster';
          img.src = firstImage;
          img.alt = merged[0].title;
          img.onerror = () => { wrap.remove(); dayEl.classList.remove('has-poster'); renderDots(dayEl, shows, merged); };
          wrap.appendChild(img);

          if (merged.length > 1) {
            const badge = document.createElement('span');
            badge.className = 'cal-poster-badge';
            badge.textContent = merged.length;
            wrap.appendChild(badge);
          }
          dayEl.appendChild(wrap);
        } else {
          renderDots(dayEl, shows, merged);
        }

        dayEl.addEventListener('click', () => onDayClick(dateStr));
      }

      weekDays.appendChild(dayEl);
    });

    weekRow.appendChild(weekDays);
    weeksEl.appendChild(weekRow);
  });

  document.getElementById('no-results').classList.toggle('hidden', hasAnyShow || state.allShows.length === 0);

  // Update show panel
  if (state.selectedDate && grouped[state.selectedDate]) {
    renderPanel(state.selectedDate, grouped[state.selectedDate]);
  } else {
    hidePanel();
  }
}

// ===== Day click =====
function onDayClick(dateStr) {
  state.selectedDate = state.selectedDate === dateStr ? null : dateStr;
  renderCalendar();
}

// ===== Show Panel =====
function renderPanel(dateStr, shows) {
  const panel = document.getElementById('show-panel');
  const dateEl = document.getElementById('panel-date');
  const cardsEl = document.getElementById('panel-cards');

  const [, month, day] = dateStr.split('-');
  const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
  const wd = weekdays[new Date(dateStr).getDay()];
  dateEl.textContent = `${+month}月${+day}日　週${wd}　${mergeSessionsForDay(shows).length} 部節目`;

  cardsEl.innerHTML = '';
  mergeSessionsForDay(shows).forEach(show => {
    const card = document.createElement('div');
    card.className = 'show-card';

    if (show.image_url) {
      const poster = document.createElement('img');
      poster.className = 'show-poster';
      poster.src = show.image_url;
      poster.alt = show.title;
      poster.onerror = () => poster.remove();
      card.appendChild(poster);
    }

    const title = document.createElement('span');
    title.className = 'show-title';
    title.textContent = show.title;
    title.title = show.title;
    card.appendChild(title);

    const venue = shortVenue(show.venue);
    const meta = document.createElement('span');
    meta.className = 'show-meta';
    meta.textContent = `📍 ${venue}`;
    card.appendChild(meta);

    const timeChips = document.createElement('div');
    timeChips.className = 'time-chips';
    show.times.forEach(t => {
      const chip = document.createElement('span');
      chip.className = 'time-chip';
      chip.textContent = t;
      timeChips.appendChild(chip);
    });
    card.appendChild(timeChips);

    const safeUrl = show.url && show.url.startsWith('https://') ? show.url : null;
    if (safeUrl) {
      const btn = document.createElement('a');
      btn.className = 'buy-btn';
      btn.href = safeUrl;
      btn.target = '_blank';
      btn.rel = 'noopener noreferrer';
      btn.textContent = '購票';
      card.appendChild(btn);
    }

    cardsEl.appendChild(card);
  });

  panel.classList.remove('hidden');
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function hidePanel() {
  document.getElementById('show-panel').classList.add('hidden');
}

// ===== Event listeners =====
document.getElementById('prev-month').addEventListener('click', () => {
  state.selectedDate = null;
  if (state.month === 0) { state.year--; state.month = 11; } else { state.month--; }
  renderCalendar();
});

document.getElementById('next-month').addEventListener('click', () => {
  state.selectedDate = null;
  if (state.month === 11) { state.year++; state.month = 0; } else { state.month++; }
  renderCalendar();
});

document.getElementById('filter-region').addEventListener('change', e => {
  state.filterRegion = e.target.value;
  state.selectedDate = null;
  renderCalendar();
});

document.getElementById('filter-search').addEventListener('input', e => {
  state.filterSearch = e.target.value.trim();
  state.selectedDate = null;
  renderCalendar();
});

// ===== Init =====
loadShows();
