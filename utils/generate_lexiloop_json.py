#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate LexiLoop word-list JSON files from the bundled german.json /
english.json source decks (data/word_lists/german.json or english.json).

Source: https://github.com/vbvss199/Language-Learning-decks

Usage
-----
  # Vocabulary mode (word + translation + bilingual example) — default
  python3 utils/generate_lexiloop_json.py --lang german --user bahman
  python3 utils/generate_lexiloop_json.py --lang english --user bahman

  # Sentence mode (German sentence as the word, English sentence as definition)
  python3 utils/generate_lexiloop_json.py --lang german --user bahman --sentences

  # Single CEFR level only
  python3 utils/generate_lexiloop_json.py --lang german --user bahman --cefr B1
  python3 utils/generate_lexiloop_json.py --lang german --user bahman --sentences --cefr A1

Output
------
  Vocabulary mode:
    data/word_lists/<user>_<lang>_<level>.json
    e.g. bahman_german_a1.json

  Sentence mode:
    data/word_lists/<user>_<lang>_sentences_<level>.json
    e.g. bahman_german_sentences_a1.json

Vocabulary mode — word format
------------------------------
  German nouns  → "der/die/das Word"   (article derived from gender field)
  Everything else → bare word as-is
  Definition: line 1 = english_translation
              line 2 = "native sentence — english sentence"

Sentence mode — word format
-----------------------------
  word       = example_sentence_native  (e.g. "Er will Arzt sein.")
  definition = example_sentence_english (e.g. "He wants to be a doctor.")
  Only records that have both sentences are included.
"""
import os
import sys
import json
import argparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORD_LISTS_DIR = os.path.join(_ROOT, 'data', 'word_lists')

GENDER_ARTICLE = {
    'masculine': 'der',
    'feminine':  'die',
    'neuter':    'das',
}

_POS_NORM = {
    'adj': 'adjective', 'adjektiv': 'adjective',
    'adv': 'adverb',
    'num': 'numeral', 'number': 'numeral',
    'v': 'verb', 'v1': 'verb',
    'n': 'noun',
    'none': '', 'unclear': '', 'discard': '',
    '[keep as-is]': '', '[as-is]': '', '[pos_edited]': '',
}

VALID_CEFR = {'A1', 'A2', 'B1', 'B2', 'C1', 'C2'}


def normalize_pos(raw):
    return _POS_NORM.get(raw, raw).lower().strip()


def build_vocab_entry(record, lang):
    word = record.get('word', '').strip()
    if not word:
        return None

    translation = record.get('english_translation', '').strip()
    pos = normalize_pos(record.get('pos', ''))
    gender = record.get('gender', '')
    native_sent = record.get('example_sentence_native', '').strip()
    english_sent = record.get('example_sentence_english', '').strip()

    if lang == 'german' and pos == 'noun':
        article = GENDER_ARTICLE.get(gender, '')
        word_field = f'{article} {word}' if article else word
    else:
        word_field = word

    definition = []
    if translation:
        definition.append(translation)
    if native_sent and english_sent:
        definition.append(f'{native_sent} — {english_sent}')
    elif english_sent and lang != 'german':
        definition.append(english_sent)

    if not definition:
        return None

    return {
        'word': word_field,
        'definition': definition if len(definition) > 1 else definition[0],
    }


def build_sentence_entry(record):
    native = record.get('example_sentence_native', '').strip()
    english = record.get('example_sentence_english', '').strip()
    if not native or not english:
        return None
    return {'word': native, 'definition': english}


def generate(lang, user, cefr_filter=None, sentences=False):
    source_path = os.path.join(WORD_LISTS_DIR, f'{lang}.json')
    if not os.path.exists(source_path):
        print(f'Source file not found: {source_path}', file=sys.stderr)
        sys.exit(1)

    with open(source_path, encoding='utf-8') as f:
        records = json.load(f)

    buckets = {}
    skipped = 0
    for record in records:
        level = record.get('cefr_level', '').strip().upper()
        if level not in VALID_CEFR:
            skipped += 1
            continue
        if cefr_filter and level != cefr_filter.upper():
            continue
        entry = build_sentence_entry(record) if sentences else build_vocab_entry(record, lang)
        if entry is None:
            skipped += 1
            continue
        buckets.setdefault(level, []).append(entry)

    if not buckets:
        print('No entries matched the given filters.')
        return

    os.makedirs(WORD_LISTS_DIR, exist_ok=True)
    for level in sorted(buckets):
        entries = buckets[level]
        kind = 'sentences_' if sentences else ''
        out_name = f'{user}_{lang}_{kind}{level.lower()}.json'
        out_path = os.path.join(WORD_LISTS_DIR, out_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        print(f'  {level}: {len(entries):>5} entries  →  {out_name}')

    if skipped:
        print(f'  (skipped {skipped} entries with missing/invalid data)')
    suffix = '_sentences_a1' if sentences else '_a1'
    print(f'\nDone. Run: ./lexiloop.sh practice --user {user} --lang {lang}{suffix}')


def main():
    parser = argparse.ArgumentParser(
        description='Generate LexiLoop JSON word lists from the bundled source decks.'
    )
    parser.add_argument('--lang', required=True, choices=['german', 'english'],
                        help='Source deck language.')
    parser.add_argument('--user', required=True,
                        help='Username prefix for output filenames (e.g. bahman).')
    parser.add_argument('--cefr', metavar='LEVEL',
                        help='Only generate one CEFR level (A1/A2/B1/B2/C1/C2).')
    parser.add_argument('--sentences', action='store_true',
                        help='Sentence mode: word = German sentence, definition = English sentence.')
    args = parser.parse_args()

    mode = 'sentence' if args.sentences else 'vocabulary'
    print(f'Generating {args.lang.upper()} {mode} lists for user "{args.user}"...')
    if args.cefr:
        print(f'Filtering to CEFR level: {args.cefr.upper()}')
    generate(args.lang, args.user, args.cefr, args.sentences)


if __name__ == '__main__':
    main()
