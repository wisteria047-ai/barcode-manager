// i18n — 多言語切替モジュール
const I18n = (() => {
  let currentLang = 'ja';
  let translations = {};
  const listeners = [];

  async function load(lang) {
    try {
      const res = await fetch(`./locales/${lang}.json`);
      if (!res.ok) throw new Error(`Failed to load ${lang}.json`);
      translations[lang] = await res.json();
    } catch (e) {
      console.error(`[i18n] Failed to load locale: ${lang}`, e);
    }
  }

  async function init(lang) {
    currentLang = lang || 'ja';
    await Promise.all([load('ja'), load('en')]);
  }

  function t(key, params) {
    const keys = key.split('.');
    let value = translations[currentLang];
    for (const k of keys) {
      if (value == null) return key;
      value = value[k];
    }
    if (value == null) return key;
    if (params) {
      return value.replace(/\{(\w+)\}/g, (_, name) =>
        params[name] != null ? params[name] : `{${name}}`
      );
    }
    return value;
  }

  async function setLang(lang) {
    if (!translations[lang]) await load(lang);
    currentLang = lang;
    listeners.forEach((fn) => fn(lang));
  }

  function getLang() {
    return currentLang;
  }

  function onChange(fn) {
    listeners.push(fn);
  }

  function offChange(fn) {
    const idx = listeners.indexOf(fn);
    if (idx >= 0) listeners.splice(idx, 1);
  }

  // data-i18n 属性を持つ要素を一括翻訳
  function translatePage() {
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      el.textContent = t(key);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      const key = el.getAttribute('data-i18n-placeholder');
      el.placeholder = t(key);
    });
    document.querySelectorAll('[data-i18n-title]').forEach((el) => {
      const key = el.getAttribute('data-i18n-title');
      el.title = t(key);
    });
    document.querySelectorAll('[data-i18n-aria]').forEach((el) => {
      const key = el.getAttribute('data-i18n-aria');
      el.setAttribute('aria-label', t(key));
    });
  }

  return { init, t, setLang, getLang, onChange, offChange, translatePage };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = I18n;
}
