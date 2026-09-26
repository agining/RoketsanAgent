import type { ReactNode } from 'react';

const ID_PATTERN = /(T\d{4}|img_\d{6}(?:_v\d+|_trk_T\d{4})?)/g;
const IS_ID = /^(T\d{4}|img_\d{6}(?:_v\d+|_trk_T\d{4})?)$/;
const BOLD_PATTERN = /(\*\*[^*\n]+\*\*)/g;

function sanitizeMarkdown(text: string): string {
  return text
    .replace(/\r\n?/g, '\n')
    .replace(/\b(None|null|undefined|NaN)\b/gi, '')
    .replace(/\[\s*]/g, '')
    .replace(/\*\*\s*\*\*/g, '')
    .replace(/\(\s*\)/g, '')
    .replace(/(?:\s*[·/]\s*){2,}/g, ' · ')
    .replace(/[ \t]+([,.;:])/g, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function splitTableRow(line: string): string[] {
  return line.replace(/^\s*\|?/, '').replace(/\|?\s*$/, '').split('|').map(cell => cell.trim());
}

function isSeparatorRow(line: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function isTable(lines: string[], index: number): boolean {
  return lines[index]?.includes('|') && isSeparatorRow(lines[index + 1] ?? '');
}

function inline(text: string, onSelectId: (id: string) => void, keyPrefix: string): ReactNode[] {
  return text.split(BOLD_PATTERN).flatMap((part, partIndex) => {
    const bold = part.startsWith('**') && part.endsWith('**');
    const clean = bold ? part.slice(2, -2).trim() : part;
    if (!clean) return [];
    const nodes = clean.split(ID_PATTERN).map((piece, index) => IS_ID.test(piece)
      ? <button className="agent-id-link" key={`${keyPrefix}-${partIndex}-${index}`} onClick={() => onSelectId(piece)}>{piece}</button>
      : piece);
    return bold ? [<strong key={`${keyPrefix}-${partIndex}`}>{nodes}</strong>] : nodes;
  });
}

export function AgentMarkdown({ text, onSelectId }: { text: string; onSelectId: (id: string) => void }) {
  const lines = sanitizeMarkdown(text).split('\n');
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) { index += 1; continue; }

    const heading = /^(#{2,3})\s+(.+)$/.exec(line);
    if (heading) {
      const Tag = heading[1].length === 2 ? 'h3' : 'h4';
      blocks.push(<Tag key={index}>{inline(heading[2], onSelectId, `h-${index}`)}</Tag>);
      index += 1;
      continue;
    }

    if (isTable(lines, index)) {
      const headers = splitTableRow(lines[index]).filter(Boolean);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        const cells = splitTableRow(lines[index]);
        if (cells.some(Boolean)) rows.push(cells);
        index += 1;
      }
      if (headers.length > 1 && rows.length) {
        blocks.push(<div className="agent-table-wrap" key={`table-${index}`}><table className="agent-markdown-table">
          <thead><tr>{headers.map((cell, cellIndex) => <th key={cellIndex}>{inline(cell, onSelectId, `th-${index}-${cellIndex}`)}</th>)}</tr></thead>
          <tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{headers.map((_, cellIndex) => <td key={cellIndex}>{inline(row[cellIndex] ?? '', onSelectId, `td-${index}-${rowIndex}-${cellIndex}`)}</td>)}</tr>)}</tbody>
        </table></div>);
      }
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*]\s+/, ''));
        index += 1;
      }
      blocks.push(<ul key={`ul-${index}`}>{items.map((item, itemIndex) => <li key={itemIndex}>{inline(item, onSelectId, `ul-${index}-${itemIndex}`)}</li>)}</ul>);
      continue;
    }

    if (/^\d+[.)]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+[.)]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+[.)]\s+/, ''));
        index += 1;
      }
      blocks.push(<ol key={`ol-${index}`}>{items.map((item, itemIndex) => <li key={itemIndex}>{inline(item, onSelectId, `ol-${index}-${itemIndex}`)}</li>)}</ol>);
      continue;
    }

    const paragraph = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^(#{2,3})\s+/.test(lines[index].trim()) && !/^[-*]\s+/.test(lines[index].trim()) && !/^\d+[.)]\s+/.test(lines[index].trim()) && !isTable(lines, index)) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push(<p key={`p-${index}`}>{inline(paragraph.join(' '), onSelectId, `p-${index}`)}</p>);
  }

  return <div className="agent-markdown">{blocks}</div>;
}
