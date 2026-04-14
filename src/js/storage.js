// storage — IndexedDB永続化モジュール（Dexie.js）
const Storage = (() => {
  let db;

  function init() {
    // Dexie がグローバルに読み込まれている前提
    db = new Dexie('BarcodeManagerDB');
    db.version(1).stores({
      items: '++id, *columns',
      settings: 'key',
      columns: '++id, order',
      history: '++id, timestamp',
    });
    return db;
  }

  function getDb() {
    if (!db) init();
    return db;
  }

  // --- Items ---
  async function getAllItems() {
    return getDb().items.toArray();
  }

  async function getItemById(id) {
    return getDb().items.get(id);
  }

  async function addItem(data) {
    const now = new Date().toISOString();
    return getDb().items.add({ ...data, _createdAt: now, _updatedAt: now });
  }

  async function addItems(dataArray) {
    const now = new Date().toISOString();
    const items = dataArray.map((d) => ({ ...d, _createdAt: now, _updatedAt: now }));
    return getDb().items.bulkAdd(items);
  }

  async function updateItem(id, changes) {
    const now = new Date().toISOString();
    return getDb().items.update(id, { ...changes, _updatedAt: now });
  }

  async function deleteItem(id) {
    return getDb().items.delete(id);
  }

  async function clearItems() {
    return getDb().items.clear();
  }

  async function countItems() {
    return getDb().items.count();
  }

  // --- Settings ---
  async function getSetting(key, defaultValue) {
    const row = await getDb().settings.get(key);
    return row ? row.value : defaultValue;
  }

  async function setSetting(key, value) {
    return getDb().settings.put({ key, value });
  }

  // --- Columns ---
  async function getColumns() {
    return getDb().columns.orderBy('order').toArray();
  }

  async function setColumns(cols) {
    await getDb().columns.clear();
    return getDb().columns.bulkAdd(cols);
  }

  // --- History ---
  async function addHistory(entry) {
    return getDb().history.add({ ...entry, timestamp: new Date().toISOString() });
  }

  async function getHistory(limit = 50) {
    return getDb().history.orderBy('timestamp').reverse().limit(limit).toArray();
  }

  // --- Reset ---
  async function resetAll() {
    await getDb().items.clear();
    await getDb().settings.clear();
    await getDb().columns.clear();
    await getDb().history.clear();
  }

  return {
    init,
    getDb,
    getAllItems,
    getItemById,
    addItem,
    addItems,
    updateItem,
    deleteItem,
    clearItems,
    countItems,
    getSetting,
    setSetting,
    getColumns,
    setColumns,
    addHistory,
    getHistory,
    resetAll,
  };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = Storage;
}
