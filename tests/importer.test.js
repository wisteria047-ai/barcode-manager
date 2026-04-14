import { describe, it, expect } from 'vitest';

// importer.js の parseCSVLine / parseCsv / hasEncodingIssue をテスト
// IIFE 内なので、コア関数を再実装してテストする

// RFC 4180 準拠 CSV パーサー（importer.js からコピー）
function parseCSVLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        current += ch;
      }
    } else {
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === ',') {
        result.push(current);
        current = '';
      } else {
        current += ch;
      }
    }
  }
  result.push(current);
  return result;
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];

  const headers = parseCSVLine(lines[0]);
  const data = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length === 0) continue;
    const row = {};
    headers.forEach((h, j) => {
      row[h.trim()] = (values[j] || '').trim();
    });
    data.push(row);
  }
  return data;
}

function hasEncodingIssue(data) {
  const sample = JSON.stringify(data.slice(0, 5));
  return /\ufffd/.test(sample) || /[\x80-\x9f]/.test(sample);
}

function escapeCsvField(str) {
  if (/[,"\n\r]/.test(str)) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}

describe('parseCSVLine: RFC 4180 準拠', () => {
  it('should parse simple comma-separated values', () => {
    expect(parseCSVLine('a,b,c')).toEqual(['a', 'b', 'c']);
  });

  it('should handle quoted fields', () => {
    expect(parseCSVLine('"hello","world"')).toEqual(['hello', 'world']);
  });

  it('should handle escaped quotes (double-quote)', () => {
    expect(parseCSVLine('"say ""hello""",value')).toEqual(['say "hello"', 'value']);
  });

  it('should handle comma inside quotes', () => {
    expect(parseCSVLine('"a,b",c')).toEqual(['a,b', 'c']);
  });

  it('should handle empty fields', () => {
    expect(parseCSVLine('a,,c')).toEqual(['a', '', 'c']);
  });

  it('should handle single field', () => {
    expect(parseCSVLine('hello')).toEqual(['hello']);
  });

  it('should handle empty string', () => {
    expect(parseCSVLine('')).toEqual(['']);
  });

  it('should handle Japanese text', () => {
    expect(parseCSVLine('品名,カテゴリ,数量')).toEqual(['品名', 'カテゴリ', '数量']);
  });

  it('should handle mixed quoted and unquoted', () => {
    expect(parseCSVLine('BN-001,"ボールペン（黒）",筆記用具')).toEqual(['BN-001', 'ボールペン（黒）', '筆記用具']);
  });
});

describe('parseCsv: CSV全体パース', () => {
  it('should parse header + data rows', () => {
    const csv = '管理番号,品名\nBN-001,ボールペン\nBN-002,消しゴム';
    const result = parseCsv(csv);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ '管理番号': 'BN-001', '品名': 'ボールペン' });
    expect(result[1]).toEqual({ '管理番号': 'BN-002', '品名': '消しゴム' });
  });

  it('should return empty array for header-only CSV', () => {
    expect(parseCsv('管理番号,品名')).toEqual([]);
  });

  it('should return empty array for empty text', () => {
    expect(parseCsv('')).toEqual([]);
  });

  it('should handle Windows line endings (CRLF)', () => {
    const csv = '名前,値\r\nA,1\r\nB,2';
    const result = parseCsv(csv);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ '名前': 'A', '値': '1' });
  });

  it('should trim header and value whitespace', () => {
    const csv = ' name , value \n hello , world ';
    const result = parseCsv(csv);
    expect(result[0]).toEqual({ 'name': 'hello', 'value': 'world' });
  });

  it('should handle missing values (fewer columns than headers)', () => {
    const csv = 'a,b,c\n1,2';
    const result = parseCsv(csv);
    expect(result[0]).toEqual({ 'a': '1', 'b': '2', 'c': '' });
  });
});

describe('hasEncodingIssue: 文字化け検出', () => {
  it('should detect replacement character (U+FFFD)', () => {
    const data = [{ name: 'hello\ufffd' }];
    expect(hasEncodingIssue(data)).toBe(true);
  });

  it('should detect control characters in 0x80-0x9F range', () => {
    const data = [{ name: 'hello\x80world' }];
    expect(hasEncodingIssue(data)).toBe(true);
  });

  it('should not flag normal Japanese text', () => {
    const data = [{ name: 'ボールペン' }, { name: 'カテゴリ' }];
    expect(hasEncodingIssue(data)).toBe(false);
  });

  it('should not flag normal ASCII', () => {
    const data = [{ name: 'hello' }];
    expect(hasEncodingIssue(data)).toBe(false);
  });

  it('should check only first 5 items', () => {
    const data = Array.from({ length: 10 }, (_, i) => ({ name: `item${i}` }));
    data[7].name = 'bad\ufffd';
    // First 5 are clean, so should not detect
    expect(hasEncodingIssue(data)).toBe(false);
  });
});

describe('escapeCsvField: CSVフィールドエスケープ', () => {
  it('should not escape plain text', () => {
    expect(escapeCsvField('hello')).toBe('hello');
  });

  it('should escape field with comma', () => {
    expect(escapeCsvField('a,b')).toBe('"a,b"');
  });

  it('should escape field with quote', () => {
    expect(escapeCsvField('say "hi"')).toBe('"say ""hi"""');
  });

  it('should escape field with newline', () => {
    expect(escapeCsvField('line1\nline2')).toBe('"line1\nline2"');
  });

  it('should handle empty string', () => {
    expect(escapeCsvField('')).toBe('');
  });
});
