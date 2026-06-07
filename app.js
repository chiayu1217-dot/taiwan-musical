// ===== State =====
const state = {
  year: new Date().getFullYear(),
  month: new Date().getMonth(), // 0-indexed
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
  if (region === '台北') return 'dot-taipei';
  if (region === '台中') return 'dot-taichung';
  if (region === '高雄') return 'dot-kaohsiung';
  return 'dot-other';
}

function pad(n) { return String(n).padStart(2, '0'); }

function toDateStr(year, month, day) {
  return `${year}-${pad(month + 1)}-${pad(day)}`;
}

// ===== Calendar rendering =====
function renderCalendar() {
  const { year, month } = state;
  const filtered = applyFilters(state.allShows);
  const grouped = groupByDate(filtered);

  // Update month label
  document.getElementById('month-label').textContent =
    `${year}年${month + 1}月`;

  // Build weeks array
  const firstDay = new Date(year, month, 1).getDay(); // 0=Sun
  // Convert to Mon-first (0=Mon ... 6=Sun)
  const startOffset = (firstDay + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const prevMonthDays = new Date(year, month, 0).getDate();

  const cells = [];
  // Leading cells from previous month
  for (let i = startOffset - 1; i >= 0; i--) {
    cells.push({ day: prevMonthDays - i, current: false });
  }
  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, current: true });
  }
  // Trailing cells
  const remainder = cells.length % 7;
  if (remainder > 0) {
    for (let d = 1; d <= 7 - remainder; d++) {
      cells.push({ day: d, current: false });
    }
  }

  // Split into weeks
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7));
  }

  const today = new Date();
  const todayStr = toDateStr(today.getFullYear(), today.getMonth(), today.getDate());

  const weeksEl = document.getElementById('weeks');
  weeksEl.innerHTML = '';

  let hasAnyShow = false;

  weeks.forEach((week, wi) => {
    const weekRow = document.createElement('div');
    weekRow.className = 'week-row';
    weekRow.dataset.week = wi;

    // Days
    const weekDays = document.createElement('div');
    weekDays.className = 'week-days';

    week.forEach(cell => {
      const dateStr = cell.current
        ? toDateStr(year, month, cell.day)
        : null;
      const shows = dateStr ? (grouped[dateStr] || []) : [];
      if (shows.length > 0) hasAnyShow = true;

      const dayEl = document.createElement('div');
      dayEl.className = 'day-cell';
      if (!cell.current) dayEl.classList.add('other-month');
      if (dateStr === todayStr) dayEl.classList.add('today');
      if (shows.length > 0) dayEl.classList.add('has-shows');
      if (dateStr === state.selectedDate) dayEl.classList.add('expanded');
      if (dateStr) dayEl.dataset.date = dateStr;
      if (dateStr) dayEl.dataset.week = wi;

      const numEl = document.createElement('span');
      numEl.className = 'day-num';
      numEl.textContent = cell.day;
      dayEl.appendChild(numEl);

      if (shows.length > 0) {
        const dotsEl = document.createElement('div');
        dotsEl.className = 'dots';
        // One dot per unique region
        const regions = [...new Set(shows.map(s => s.region))];
        regions.forEach(region => {
          const dot = document.createElement('span');
          dot.className = `dot ${dotClass(region)}`;
          dotsEl.appendChild(dot);
        });
        dayEl.appendChild(dotsEl);

        dayEl.addEventListener('click', () => onDayClick(dateStr, wi));
      }

      weekDays.appendChild(dayEl);
    });

    // Expand panel
    const expandEl = document.createElement('div');
    expandEl.className = 'week-expand';
    expandEl.id = `expand-${wi}`;

    weekRow.appendChild(weekDays);
    weekRow.appendChild(expandEl);
    weeksEl.appendChild(weekRow);
  });

  // Restore expanded state
  if (state.selectedDate) {
    const selCell = weeksEl.querySelector(`.day-cell[data-date="${state.selectedDate}"]`);
    if (selCell) {
      const wi = selCell.dataset.week;
      openExpand(state.selectedDate, wi, grouped);
    }
  }

  // No results message
  document.getElementById('no-results').classList.toggle('hidden', hasAnyShow || state.allShows.length === 0);
}

// ===== Expand/collapse =====
function onDayClick(dateStr, weekIndex) {
  if (state.selectedDate === dateStr) {
    state.selectedDate = null;
  } else {
    state.selectedDate = dateStr;
  }
  renderCalendar();
}

function openExpand(dateStr, weekIndex, grouped) {
  const expandEl = document.getElementById(`expand-${weekIndex}`);
  if (!expandEl) return;

  const shows = grouped[dateStr] || [];
  const [year, month, day] = dateStr.split('-');
  expandEl.innerHTML = `<div class="expand-title">${+month}月${+day}日 ${shows.length} 場次</div>`;

  shows.forEach(show => {
    const card = document.createElement('div');
    card.className = 'show-card';

    const title = document.createElement('span');
    title.className = 'show-title';
    title.textContent = show.title;

    const meta = document.createElement('span');
    meta.className = 'show-meta';
    meta.textContent = `📍 ${show.venue}   🕐 ${show.time}`;

    card.appendChild(title);
    card.appendChild(meta);

    if (show.price) {
      const price = document.createElement('span');
      price.className = 'show-price';
      price.textContent = `NT$ ${show.price}`;
      card.appendChild(price);
    }

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

    expandEl.appendChild(card);
  });

  expandEl.classList.add('open');

  // Mark selected cell
  const selCell = document.querySelector(`.day-cell[data-date="${dateStr}"]`);
  if (selCell) selCell.classList.add('expanded');
}

// ===== Event listeners =====
document.getElementById('prev-month').addEventListener('click', () => {
  state.selectedDate = null;
  if (state.month === 0) { state.year--; state.month = 11; }
  else { state.month--; }
  renderCalendar();
});

document.getElementById('next-month').addEventListener('click', () => {
  state.selectedDate = null;
  if (state.month === 11) { state.year++; state.month = 0; }
  else { state.month++; }
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
