"""Local, page-addressable PDF inventory and OCR for reference-book research."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.local' / 'reference-books'
SOURCES = ROOT / '02_公共资产库' / '参考图书'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def inventory():
    import pypdfium2 as pdf
    books = []
    for number, source in enumerate(sorted(SOURCES.glob('*.pdf')), 1):
        with pdf.PdfDocument(source) as doc:
            chars = []
            for page in doc:
                text = page.get_textpage()
                try:
                    chars.append(len(text.get_text_range().strip()))
                finally:
                    text.close()
                page.close()
            books.append(dict(id=f'B{number:02d}', file=source.relative_to(ROOT).as_posix(),
                              pages=len(doc), bytes=source.stat().st_size,
                              sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                              text_pages=sum(n > 40 for n in chars), characters=sum(chars)))
    save(CACHE / 'inventory.json', books)
    print(json.dumps(books, ensure_ascii=False, indent=2))


def page_numbers(value):
    numbers = set()
    for part in value.split(','):
        bounds = part.strip().split('-')
        if len(bounds) == 1:
            numbers.add(int(bounds[0]))
        elif len(bounds) == 2 and int(bounds[0]) <= int(bounds[1]):
            numbers.update(range(int(bounds[0]), int(bounds[1]) + 1))
        else:
            raise ValueError(f'Invalid page range: {part}')
    if not numbers or min(numbers) < 1:
        raise ValueError('PDF page numbers start at 1')
    return sorted(numbers)


def ocr(book_id, requested, scale):
    import numpy as np
    import pypdfium2 as pdf
    from rapidocr_onnxruntime import RapidOCR
    books = json.loads((CACHE / 'inventory.json').read_text(encoding='utf-8'))
    book = next((b for b in books if b['id'] == book_id), None)
    if book is None:
        raise ValueError('Unknown book ID; run inventory first')
    source = ROOT / book['file']
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    if fingerprint != book['sha256']:
        raise ValueError('Source changed; regenerate inventory before OCR')
    numbers = page_numbers(requested)
    # Include engine/render settings in the cache identity.
    target = CACHE / 'ocr' / fingerprint / f'rapidocr-1.4.4-scale-{scale:g}'
    engine = None
    with pdf.PdfDocument(source) as doc:
        if max(numbers) > len(doc):
            raise ValueError(f'Page range exceeds {len(doc)} PDF pages')
        for number in numbers:
            dest = target / f'p{number:04d}.json'
            if dest.exists():
                print(f'{book_id} PDF {number}: cached', flush=True)
                continue
            if engine is None:
                engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)
            page = doc[number - 1]
            try:
                bitmap = page.render(scale=scale)
                im = bitmap.to_pil().convert('RGB')
                target.mkdir(parents=True, exist_ok=True)
                im.save(target / f'p{number:04d}.png')
                result, elapsed = engine(np.array(im))
                lines = [{'box': row[0], 'text': row[1], 'confidence': float(row[2])}
                         for row in (result or [])]
                save(dest, {'source_sha256': fingerprint, 'pdf_page': number,
                            'engine': 'rapidocr_onnxruntime 1.4.4', 'scale': scale,
                            'lines': lines, 'text': '\n'.join(r['text'] for r in lines),
                            'warning': 'Machine OCR; verify claims against the rendered page.'})
                bitmap.close()
            finally:
                page.close()
            print(f'{book_id} PDF {number}: {len(lines)} lines', flush=True)


def show(book_id, requested):
    books = json.loads((CACHE / 'inventory.json').read_text(encoding='utf-8'))
    book = next(b for b in books if b['id'] == book_id)
    for number in page_numbers(requested):
        matches = sorted((CACHE / 'ocr' / book['sha256']).glob(f'*/p{number:04d}.json'))
        if not matches:
            raise FileNotFoundError(f'{book_id} PDF {number}: OCR not available')
        record = json.loads(matches[-1].read_text(encoding='utf-8'))
        print(f'\n--- {book_id} PDF {number} ---\n{record["text"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inventory', 'ocr', 'show'])
    parser.add_argument('--book')
    parser.add_argument('--pages', help='1-based PDF pages, e.g. 4,7-10')
    parser.add_argument('--scale', type=float, default=2.0)
    args = parser.parse_args()
    if args.action == 'inventory':
        inventory()
    else:
        if not args.book or not args.pages:
            parser.error('--book and --pages are required')
        if args.scale <= 0 or args.scale > 4:
            parser.error('--scale must be in (0,4]')
        if args.action == 'ocr':
            ocr(args.book, args.pages, args.scale)
        else:
            show(args.book, args.pages)


if __name__ == '__main__':
    main()
