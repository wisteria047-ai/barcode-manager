// table — テーブル表示・編集・ソート・ページネーション
const Table = (() => {
  let allItems = [];
  let filteredItems = [];
  let columns = [];
  let currentPage = 1;
  let pageSize = 20;
  let sortColumn = null;
  let sortDirection = null; // 'asc' | 'desc' | null
  let selectedIds = new Set();
  let editingRowId = null;
  let editingData = {};
  const MAX_COLUMNS = 30;

  // --- 初期化 ---
  async function init() {
    const savedPageSize = await Storage.getSetting('pageSize', 20);
    pageSize = savedPageSize;
    const pageSizeSelect = document.getElementById('page-size-select');
    if (pageSizeSelect) pageSizeSelect.value = String(pageSize);

    bindEvents();
    await loadData();
  }

  function bindEvents() {
    document.getElementById('page-size-select')?.addEventListener('change', (e) => {
      pageSize = parseInt(e.target.value, 10);
      currentPage = 1;
      Storage.setSetting('pageSize', pageSize);
      render();
    });
    document.getElementById('btn-prev-page')?.addEventListener('click', () => {
      if (currentPage > 1) { currentPage--; render(); }
    });
    document.getElementById('btn-next-page')?.addEventListener('click', () => {
      if (currentPage < getTotalPages()) { currentPage++; render(); }
    });
    document.getElementById('search-input')?.addEventListener('input', (e) => {
      applyFilter(e.target.value);
    });
    document.getElementById('status-filter')?.addEventListener('change', () => {
      applyFilter(document.getElementById('search-input')?.value || '');
    });
    document.getElementById('btn-deselect-all')?.addEventListener('click', () => {
      selectedIds.clear();
      updateSelectionBar();
      render();
    });
  }

  // --- データ読み込み ---
  async function loadData() {
    allItems = await Storage.getAllItems();
    columns = await Storage.getColumns();
    if (columns.length === 0 && allItems.length > 0) {
      columns = inferColumns(allItems);
      await Storage.setColumns(columns);
    }
    applyFilter('');
  }

  function inferColumns(items) {
    const keys = new Set();
    items.forEach((item) => {
      Object.keys(item).forEach((k) => {
        if (!k.startsWith('_') && k !== 'id') keys.add(k);
      });
    });
    return Array.from(keys).map((key, i) => ({
      key,
      name: key,
      visible: true,
      width: null,
      order: i,
    }));
  }

  // --- フィルター ---
  function applyFilter(searchText) {
    const statusValue = document.getElementById('status-filter')?.value || '';
    const query = searchText.toLowerCase().trim();

    filteredItems = allItems.filter((item) => {
      if (statusValue && item._status !== statusValue) return false;
      if (!query) return true;
      return columns.some((col) => {
        const val = item[col.key];
        return val != null && String(val).toLowerCase().includes(query);
      });
    });

    if (sortColumn) {
      applySortToFiltered();
    }

    currentPage = 1;
    render();
  }

  // --- ソート ---
  function toggleSort(colKey) {
    if (sortColumn === colKey) {
      if (sortDirection === 'asc') sortDirection = 'desc';
      else if (sortDirection === 'desc') { sortColumn = null; sortDirection = null; }
    } else {
      sortColumn = colKey;
      sortDirection = 'asc';
    }
    if (sortColumn) applySortToFiltered();
    else applyFilter(document.getElementById('search-input')?.value || '');
    render();
  }

  function applySortToFiltered() {
    filteredItems.sort((a, b) => {
      const va = a[sortColumn] ?? '';
      const vb = b[sortColumn] ?? '';
      const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
      return sortDirection === 'desc' ? -cmp : cmp;
    });
  }

  // --- ページネーション ---
  function getTotalPages() {
    return Math.max(1, Math.ceil(filteredItems.length / pageSize));
  }

  function getPageItems() {
    const start = (currentPage - 1) * pageSize;
    return filteredItems.slice(start, start + pageSize);
  }

  // --- レンダリング ---
  function render() {
    const hasData = allItems.length > 0;
    const emptyState = document.getElementById('empty-state');
    const dataTable = document.getElementById('data-table');
    const pagination = document.getElementById('pagination');

    if (!hasData) {
      emptyState.style.display = '';
      dataTable.style.display = 'none';
      pagination.style.display = 'none';
      updateStatusBar();
      return;
    }

    emptyState.style.display = 'none';
    dataTable.style.display = '';
    pagination.style.display = '';

    renderHead();
    renderBody();
    renderPagination();
    updateStatusBar();
    updateSelectionBar();
  }

  function renderHead() {
    const thead = document.getElementById('table-head');
    const visibleCols = columns.filter((c) => c.visible !== false);
    const allChecked = filteredItems.length > 0 && filteredItems.every((item) => selectedIds.has(item.id));

    let html = '<tr>';
    html += `<th scope="col" style="width:40px;"><input type="checkbox" class="row-checkbox" id="select-all" aria-label="${I18n.t('table.selectAll')}" ${allChecked ? 'checked' : ''}></th>`;
    html += `<th scope="col" style="width:50px;" data-i18n="table.noColumn">${I18n.t('table.noColumn')}</th>`;

    visibleCols.forEach((col) => {
      const isSorted = sortColumn === col.key;
      const indicator = isSorted ? (sortDirection === 'asc' ? ' ▲' : ' ▼') : '';
      const widthStyle = col.width ? `width:${col.width}px;` : '';
      html += `<th scope="col" data-col-key="${col.key}" style="${widthStyle}" draggable="true">`;
      html += `<span class="col-name">${col.name}</span>`;
      if (indicator) html += `<span class="sort-indicator">${indicator}</span>`;
      html += `<button class="col-delete-btn" data-col-delete="${col.key}" aria-label="${I18n.t('column.deleteBtn')}" title="${I18n.t('column.deleteBtn')}">✕</button>`;
      html += `<div class="col-resize-handle" data-col-key="${col.key}"></div>`;
      html += '</th>';
    });

    html += `<th scope="col" style="width:100px;">${I18n.t('table.status')}</th>`;
    html += `<th scope="col" style="width:100px;" data-i18n="table.actions">${I18n.t('table.actions')}</th>`;
    html += '</tr>';
    thead.innerHTML = html;

    // イベント: 全選択
    document.getElementById('select-all')?.addEventListener('change', (e) => {
      if (e.target.checked) {
        filteredItems.forEach((item) => selectedIds.add(item.id));
      } else {
        selectedIds.clear();
      }
      updateSelectionBar();
      render();
    });

    // イベント: ソート（ヘッダークリック）
    thead.querySelectorAll('th[data-col-key]').forEach((th) => {
      th.addEventListener('click', (e) => {
        if (e.target.classList.contains('col-resize-handle')) return;
        toggleSort(th.dataset.colKey);
      });

      // ダブルクリック: カラム名変更
      th.addEventListener('dblclick', (e) => {
        if (e.target.classList.contains('col-resize-handle')) return;
        startColumnRename(th.dataset.colKey, th);
      });
    });

    // イベント: カラムD&D並び替え
    let dragColKey = null;
    thead.querySelectorAll('th[data-col-key]').forEach((th) => {
      th.addEventListener('dragstart', (e) => {
        dragColKey = th.dataset.colKey;
        th.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
      });
      th.addEventListener('dragend', () => {
        th.classList.remove('dragging');
        thead.querySelectorAll('th').forEach((t) => t.classList.remove('drag-over'));
      });
      th.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        th.classList.add('drag-over');
      });
      th.addEventListener('dragleave', () => {
        th.classList.remove('drag-over');
      });
      th.addEventListener('drop', async (e) => {
        e.preventDefault();
        th.classList.remove('drag-over');
        const targetKey = th.dataset.colKey;
        if (!dragColKey || dragColKey === targetKey) return;
        const fromIdx = columns.findIndex((c) => c.key === dragColKey);
        const toIdx = columns.findIndex((c) => c.key === targetKey);
        if (fromIdx < 0 || toIdx < 0) return;
        const [moved] = columns.splice(fromIdx, 1);
        columns.splice(toIdx, 0, moved);
        columns.forEach((c, i) => { c.order = i; });
        await Storage.setColumns(columns);
        render();
      });
    });

    // イベント: カラム削除ボタン
    thead.querySelectorAll('.col-delete-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteColumn(btn.dataset.colDelete);
      });
    });

    // イベント: カラムリサイズ
    thead.querySelectorAll('.col-resize-handle').forEach((handle) => {
      handle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        startColumnResize(handle.dataset.colKey, e);
      });
    });
  }

  function renderBody() {
    const tbody = document.getElementById('table-body');
    const pageItems = getPageItems();
    const visibleCols = columns.filter((c) => c.visible !== false);
    const startIndex = (currentPage - 1) * pageSize;

    let html = '';
    pageItems.forEach((item, i) => {
      const isSelected = selectedIds.has(item.id);
      const isEditing = editingRowId === item.id;
      const rowClass = isSelected ? 'selected' : '';

      html += `<tr class="${rowClass}" data-id="${item.id}">`;
      html += `<td><input type="checkbox" class="row-checkbox" data-id="${item.id}" ${isSelected ? 'checked' : ''}></td>`;
      html += `<td>${startIndex + i + 1}</td>`;

      visibleCols.forEach((col) => {
        const val = item[col.key] ?? '';
        if (isEditing) {
          html += `<td><input type="text" class="inline-edit-input" data-key="${col.key}" value="${escapeHtml(String(val))}"></td>`;
        } else {
          html += `<td>${escapeHtml(String(val))}</td>`;
        }
      });

      // ステータス列
      const status = item._status || 'available';
      const isOverdue = status === 'lent' && item._dueDate && new Date(item._dueDate) < new Date();
      const badgeClass = isOverdue ? 'overdue' : status;
      const statusLabel = isOverdue
        ? I18n.t('lending.overdue')
        : I18n.t(`lending.status${status.charAt(0).toUpperCase() + status.slice(1)}`) || status;
      let statusCell = `<span class="status-badge status-badge--${badgeClass}">${statusLabel}</span>`;
      if (status === 'lent' && item._lentTo) {
        statusCell += `<div class="lent-info">${escapeHtml(item._lentTo)}</div>`;
      }
      html += `<td>${statusCell}</td>`;

      if (isEditing) {
        html += `<td>
          <button class="action-btn action-btn--save" data-action="save" data-id="${item.id}">${I18n.t('table.saveBtn')}</button>
          <button class="action-btn action-btn--cancel" data-action="cancel">${I18n.t('table.cancelBtn')}</button>
        </td>`;
      } else {
        html += `<td>
          <button class="action-btn" data-action="edit" data-id="${item.id}">${I18n.t('table.editBtn')}</button>
          <button class="action-btn action-btn--delete" data-action="delete" data-id="${item.id}">${I18n.t('table.deleteBtn')}</button>
        </td>`;
      }
      html += '</tr>';
    });

    tbody.innerHTML = html;

    // イベント: チェックボックス
    tbody.querySelectorAll('.row-checkbox').forEach((cb) => {
      cb.addEventListener('change', (e) => {
        const id = parseInt(e.target.dataset.id, 10);
        if (e.target.checked) selectedIds.add(id);
        else selectedIds.delete(id);
        updateSelectionBar();
        render();
      });
    });

    // イベント: アクションボタン
    tbody.querySelectorAll('[data-action]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const action = btn.dataset.action;
        const id = parseInt(btn.dataset.id, 10);
        if (action === 'edit') startEdit(id);
        else if (action === 'save') saveEdit(id);
        else if (action === 'cancel') cancelEdit();
        else if (action === 'delete') deleteRow(id);
      });
    });
  }

  function renderPagination() {
    const total = filteredItems.length;
    const totalPages = getTotalPages();
    const start = (currentPage - 1) * pageSize + 1;
    const end = Math.min(currentPage * pageSize, total);

    document.getElementById('pagination-info-text').textContent =
      `${start}–${end} / ${total}`;
    document.getElementById('page-indicator').textContent =
      `${currentPage} / ${totalPages}`;

    document.getElementById('btn-prev-page').disabled = currentPage <= 1;
    document.getElementById('btn-next-page').disabled = currentPage >= totalPages;
  }

  function updateStatusBar() {
    const total = allItems.length;
    const displayed = filteredItems.length;
    const collected = allItems.filter((i) => i._status === 'collected').length;
    const returned = allItems.filter((i) => i._status === 'returned').length;
    document.getElementById('status-total').textContent = I18n.t('status.totalItems', { total });
    document.getElementById('status-collected').textContent = I18n.t('status.collected', { count: collected });
    document.getElementById('status-returned').textContent = I18n.t('status.returned', { count: returned });
    document.getElementById('status-displayed').textContent = I18n.t('status.displayed', { count: displayed });
  }

  function updateSelectionBar() {
    const bar = document.getElementById('selection-bar');
    const count = selectedIds.size;
    if (count > 0) {
      bar.classList.add('visible');
      document.getElementById('selection-count').textContent = `${count} / ${allItems.length}`;
      document.getElementById('btn-edit-selected').disabled = false;
      document.getElementById('btn-delete-selected').disabled = false;
    } else {
      bar.classList.remove('visible');
      document.getElementById('btn-edit-selected').disabled = true;
      document.getElementById('btn-delete-selected').disabled = true;
    }
  }

  // --- インライン編集 ---
  function startEdit(id) {
    editingRowId = id;
    render();
    // 最初のinputにフォーカス
    const firstInput = document.querySelector(`.inline-edit-input`);
    if (firstInput) firstInput.focus();
  }

  async function saveEdit(id) {
    const inputs = document.querySelectorAll(`tr[data-id="${id}"] .inline-edit-input`);
    const changes = {};
    inputs.forEach((input) => {
      changes[input.dataset.key] = input.value;
    });
    await Storage.updateItem(id, changes);
    editingRowId = null;
    await loadData();
    showToast(I18n.t('import.imported', { count: 1 }), 'success');
  }

  function cancelEdit() {
    editingRowId = null;
    render();
  }

  // --- 行削除（Undo付き） ---
  async function deleteRow(id) {
    const item = allItems.find((i) => i.id === id);
    if (!item) return;

    await Storage.deleteItem(id);
    await loadData();
    showUndo(I18n.t('undo.deleted'), async () => {
      await Storage.addItem(item);
      await loadData();
    });
  }

  // --- 行追加 ---
  async function addRow() {
    const newItem = {};
    columns.forEach((col) => { newItem[col.key] = ''; });
    const id = await Storage.addItem(newItem);
    await loadData();
    // 最後のページに移動
    currentPage = getTotalPages();
    render();
    startEdit(id);
  }

  // --- カラム名変更 ---
  function startColumnRename(colKey, thElement) {
    const col = columns.find((c) => c.key === colKey);
    if (!col) return;

    const nameSpan = thElement.querySelector('.col-name');
    const oldName = col.name;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = oldName;
    input.className = 'inline-edit-input';
    input.style.width = '100%';
    nameSpan.replaceWith(input);
    input.focus();
    input.select();

    const finish = async () => {
      const newName = input.value.trim() || oldName;
      col.name = newName;
      await Storage.setColumns(columns);
      render();
    };

    input.addEventListener('blur', finish);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
      if (e.key === 'Escape') { input.value = oldName; input.blur(); }
    });
  }

  // --- カラム追加 ---
  async function addColumn() {
    if (columns.length >= MAX_COLUMNS) {
      showToast(I18n.t('column.maxReached', { max: MAX_COLUMNS }), 'error');
      return;
    }
    const key = `col_${Date.now()}`;
    const name = `${I18n.t('column.addColumn')} ${columns.length + 1}`;
    columns.push({ key, name, visible: true, width: null, order: columns.length });
    await Storage.setColumns(columns);
    render();
  }

  // --- カラム削除 ---
  async function deleteColumn(colKey) {
    const col = columns.find((c) => c.key === colKey);
    if (!col) return;

    showConfirm(
      I18n.t('column.deleteConfirm', { name: col.name }),
      I18n.t('column.deleteDescription'),
      I18n.t('column.deleteBtn'),
      async () => {
        columns = columns.filter((c) => c.key !== colKey);
        await Storage.setColumns(columns);
        // データからもカラムを削除
        for (const item of allItems) {
          if (item[colKey] !== undefined) {
            const copy = { ...item };
            delete copy[colKey];
            await Storage.updateItem(item.id, copy);
          }
        }
        await loadData();
      }
    );
  }

  // --- カラムリサイズ ---
  function startColumnResize(colKey, startEvent) {
    const col = columns.find((c) => c.key === colKey);
    if (!col) return;

    const th = document.querySelector(`th[data-col-key="${colKey}"]`);
    const startWidth = th.offsetWidth;
    const startX = startEvent.clientX;

    const onMove = (e) => {
      const diff = e.clientX - startX;
      const newWidth = Math.max(60, startWidth + diff);
      th.style.width = `${newWidth}px`;
      col.width = newWidth;
    };

    const onUp = async () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      await Storage.setColumns(columns);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // --- ユーティリティ ---
  function escapeHtml(str) {
    return UI.escapeHtml(str);
  }

  function getSelectedIds() {
    return Array.from(selectedIds);
  }

  function getColumns() {
    return columns;
  }

  function getItems() {
    return allItems;
  }

  return {
    init,
    loadData,
    render,
    addRow,
    addColumn,
    deleteColumn,
    getSelectedIds,
    getColumns,
    getItems,
    applyFilter,
  };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = Table;
}
