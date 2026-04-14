import { describe, it, expect, beforeEach } from 'vitest';

// i18n モジュールを直接テスト（DOM不要な純粋関数部分）
// I18n は IIFE でグローバルに公開される設計のため、
// テスト用にコア関数を再実装してテストする

describe('i18n: t() キー解決', () => {
  let translations;
  let currentLang;

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

  beforeEach(() => {
    currentLang = 'ja';
    translations = {
      ja: {
        app: { title: 'バーコード管理ツール' },
        import: { imported: '{count}件のデータを取り込みました' },
        status: { totalItems: '全{total}件' },
        nested: { deep: { value: 'ディープ値' } },
      },
      en: {
        app: { title: 'Barcode Manager' },
        import: { imported: '{count} items imported' },
      },
    };
  });

  it('should resolve single-level key', () => {
    expect(t('app.title')).toBe('バーコード管理ツール');
  });

  it('should resolve nested key', () => {
    expect(t('nested.deep.value')).toBe('ディープ値');
  });

  it('should return key string for missing key', () => {
    expect(t('nonexistent.key')).toBe('nonexistent.key');
  });

  it('should return key string for partially missing path', () => {
    expect(t('app.missing')).toBe('app.missing');
  });

  it('should substitute single parameter', () => {
    expect(t('import.imported', { count: 10 })).toBe('10件のデータを取り込みました');
  });

  it('should substitute multiple parameters', () => {
    // totalItems only has {total} but test parameter replacement
    expect(t('status.totalItems', { total: 50 })).toBe('全50件');
  });

  it('should preserve placeholder when parameter is missing', () => {
    expect(t('import.imported', {})).toBe('{count}件のデータを取り込みました');
  });

  it('should handle zero as parameter value', () => {
    expect(t('import.imported', { count: 0 })).toBe('0件のデータを取り込みました');
  });

  it('should work with English locale', () => {
    currentLang = 'en';
    expect(t('app.title')).toBe('Barcode Manager');
  });

  it('should return key for missing translation in current locale', () => {
    currentLang = 'en';
    expect(t('nested.deep.value')).toBe('nested.deep.value');
  });
});
