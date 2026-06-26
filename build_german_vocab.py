#!/usr/bin/env python3
"""
build_german_vocab.py

Reads data/word_lists/word_to_json.txt (one German word per line),
looks up each word on the English and German Wiktionary (1 req/s),
and writes a LexiLoop-compatible JSON file.

For nouns, the word field includes both the singular with article and
the plural: "das Auto, die Autos"

Usage:
    python3 build_german_vocab.py <output_json_path>

Example:
    python3 build_german_vocab.py data/word_lists/bahman_german_a1.json
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

INPUT_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'data', 'word_lists', 'word_to_json.txt')
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'data', 'word_lists', '.vocab_build_progress.json')

DELAY      = 1.0   # 1 request per second
MAX_RETRY  = 3
BACKOFF    = 10    # seconds, doubles on each 429

ARTICLE = {'m': 'der', 'f': 'die', 'n': 'das'}

# ------------------------------------------------------------
# HTTP
# ------------------------------------------------------------

def http_get(url, timeout=10):
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'LexiLoop-vocab-builder/1.0 (educational)'},
    )
    wait = BACKOFF
    for _ in range(MAX_RETRY):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 503):
                print(f'    rate limited ({e.code}), waiting {wait}s…', flush=True)
                time.sleep(wait)
                wait = min(wait * 2, 60)
                continue
            return None
        except Exception:
            return None
    return None


# ------------------------------------------------------------
# Wiktionary lookups
# ------------------------------------------------------------

_INFLECTION_RE = re.compile(
    r'^(plural|genitive|dative|accusative|nominative|inflected|'
    r'past tense|present tense|alternative form|archaic form)',
    re.I,
)

def en_definition(word):
    """English definition from en.wiktionary. Returns (part_of_speech, text) or None."""
    url = ('https://en.wiktionary.org/api/rest_v1/page/definition/'
           + urllib.parse.quote(word))
    data = http_get(url)
    if not data:
        return None
    for entry in data.get('de', []):
        for defn in entry.get('definitions', []):
            text = re.sub(r'<[^>]+>', '', defn.get('definition', '')).strip()
            if not text or _INFLECTION_RE.match(text):
                continue
            return entry.get('partOfSpeech', ''), text
    return None


def de_noun_info(word):
    """Article and nominative plural from de.wiktionary. Returns (article, plural) or (None, None)."""
    url = ('https://de.wiktionary.org/w/api.php?action=parse&format=json'
           f'&page={urllib.parse.quote(word)}&prop=wikitext')
    data = http_get(url)
    if not data:
        return None, None
    wikitext = data.get('parse', {}).get('wikitext', {}).get('*', '')

    article = None
    for pat in (r'\|Genus\s*=\s*([mfn])', r'\|Genus 1\s*=\s*([mfn])'):
        m = re.search(pat, wikitext)
        if m:
            article = ARTICLE.get(m.group(1))
            break

    plural = None
    # "Nominativ Plural" covers most nouns; some entries use "Nominativ Plural 1"
    for pat in (r'\|Nominativ Plural\s*=\s*([^\n|{]+)',
                r'\|Nominativ Plural 1\s*=\s*([^\n|{]+)'):
        m = re.search(pat, wikitext)
        if m:
            candidate = m.group(1).strip()
            # Wiktionary sometimes puts "—" or "-" for words with no plural
            if candidate and candidate not in ('—', '-', '–'):
                plural = candidate
            break

    return article, plural


# ------------------------------------------------------------
# Progress helpers
# ------------------------------------------------------------

def write_progress(processed, total, words, running=True, output=None):
    data = {
        'running':   running,
        'processed': processed,
        'total':     total,
        'words':     words,
    }
    if output:
        data['output'] = output
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} <output_json_path>', file=sys.stderr)
        sys.exit(1)

    output_path = sys.argv[1]

    if not os.path.exists(INPUT_FILE):
        print(f'Input file not found: {INPUT_FILE}', file=sys.stderr)
        write_progress(0, 0, [], running=False)
        sys.exit(1)

    with open(INPUT_FILE, encoding='utf-8') as f:
        raw_words = [l.strip() for l in f if l.strip() and not l.startswith('#')]

    total = len(raw_words)
    print(f'{total} words to process → {output_path}')
    write_progress(0, total, [])

    results = []

    for i, raw in enumerate(raw_words, 1):
        # Strip a leading article if the user included it
        word = raw
        m = re.match(r'^(der|die|das)\s+(.+)$', raw, re.I)
        if m:
            word = m.group(2)

        pos, defn, article, plural = None, '', None, None

        # English definition
        result = en_definition(word)
        time.sleep(DELAY)
        if result:
            pos, defn = result

        # German noun info (article + plural)
        if pos and 'noun' in pos.lower():
            article, plural = de_noun_info(word)
            time.sleep(DELAY)

        # Build the word field
        if article:
            singular = f'{article} {word}'
            if plural:
                word_field = f'{singular}, die {plural}'
            else:
                word_field = singular
        else:
            word_field = word

        entry = {'word': word_field, 'definition': defn}
        results.append(entry)

        status = '✓' if defn else '?'
        print(f'[{i}/{total}] {status}  {raw} → {word_field}: {defn[:55]}', flush=True)
        write_progress(i, total, results)

    # Write final JSON
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'\nDone. {len(results)} words saved to {output_path}')
    write_progress(total, total, results, running=False, output=output_path)


if __name__ == '__main__':
    main()
