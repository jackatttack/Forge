# -*- coding: utf-8 -*-
"""Portable workflow guides and small, deterministic full-text search.

Resources ship with Forge. No journal, network, disk cache or host adapter
is required. Only catalogue entries can be retrieved as guide files.
"""

import math
import re
from collections import Counter
from importlib import resources


# EDITABLE CATALOGUE
# Keep names stable: boot text and guide links use these identifiers.
GUIDES = (
    {
        'id': 'inspect',
        'title': 'Choose useful inspection',
        'summary': 'Choose MAP, SEARCH or READ and keep inspection bounded.',
        'keywords': 'find locate location structure content symbol source '
                    'directory directories unknown scope large files',
    },
    {
        'id': 'edit',
        'title': 'Choose a precise edit',
        'summary': 'Choose a mutation, ground its target and order dependent edits.',
        'keywords': 'change replace insert delete write copy modify mutation '
                    'anchor anchors line lines bottom upwards refactor',
    },
    {
        'id': 'recover',
        'title': 'Recover from a failed run',
        'summary': 'Interpret failures, inspect stored runs and choose recovery.',
        'keywords': 'error errors failed failure rollback undo restore revert '
                    'branch checkpoint ambiguous mismatch partial truncated',
    },
    {
        'id': 'workflow',
        'title': 'Work through the clipboard loop',
        'summary': 'Sequence bundles, verify results and test the intended runtime.',
        'keywords': 'clipboard packet loop process import imports test tests '
                    'testing checkout installed syntax reload restart handoff',
    },
    {
        'id': 'human-owned-code',
        'title': 'Write human-owned code',
        'summary': 'Keep code understandable, editable and appropriate to its host.',
        'keywords': 'readable readability maintainable naming names settings '
                    'comments docstrings simple simplicity portable pythonista',
    },
)

STOP_WORDS = set(
    'a an the and or but in on at to for of with is was are were be been '
    'have has do does did will would could should may can it its i we you '
    'my our your this that how what which when where me please forge docs '
    'guide guides'.split()
)
MAX_QUERY_CHARACTERS = 240
MAX_RESULTS = 3


def _tokens(text):
    """Keep identifiers and command text, including text inside backticks."""
    return [
        token for token in re.findall(r'[a-z0-9_]+', text.lower())
        if token not in STOP_WORDS
    ]


def catalogue():
    """Return public metadata without exposing mutable catalogue entries."""
    return [
        {key: guide[key] for key in ('id', 'title', 'summary')}
        for guide in GUIDES
    ]


def read_guide(name):
    """Read one registered guide; unknown names raise KeyError.

    Resource errors propagate so a broken installation is not reported as
    an unknown guide or an empty search.
    """
    name = name.strip().lower()
    if name not in {guide['id'] for guide in GUIDES}:
        raise KeyError(name)
    # read_text supports Python 3.8 and packaged resources, including zip imports.
    return resources.read_text(__package__, name + '.txt', encoding='utf-8')


def catalogue_text():
    """Render a small index with directly usable retrieval commands."""
    lines = [
        'FORGE DOCS',
        'Workflow guidance shipped with this Forge installation.',
        '',
    ]
    for guide in catalogue():
        lines.extend([
            'FORGE docs ' + guide['id'],
            '  ' + guide['summary'],
        ])
    lines.extend([
        '',
        'Find a guide: FORGE search docs <query>',
        'Operation syntax: FORGE help <OP> full',
        'Bundle grammar: FORGE bundle',
    ])
    return '\n'.join(lines)


def search(query):
    """Return up to three relevant guides using BM25-style term scoring.

    Exact guide identifiers and titles rank first. Metadata receives extra
    weight; guide bodies remain searchable. Ties use the stable identifier.
    The five-document index is built in memory, without filesystem writes.
    """
    query = query.strip()
    if not query:
        raise ValueError('FORGE search docs requires a query')
    if len(query) > MAX_QUERY_CHARACTERS:
        raise ValueError('Documentation queries must be at most 240 characters')

    query_terms = set(_tokens(query))
    if not query_terms:
        return []

    documents = []
    for guide in GUIDES:
        metadata = ' '.join(
            guide[key] for key in ('id', 'title', 'summary', 'keywords')
        )
        terms = _tokens(metadata + ' ' + metadata + ' ' + read_guide(guide['id']))
        documents.append(Counter(terms))

    document_count = len(documents)
    lengths = [sum(document.values()) for document in documents]
    average_length = sum(lengths) / max(document_count, 1)
    frequencies = Counter()
    for document in documents:
        frequencies.update(document.keys())

    ranked = []
    for guide, document, length in zip(GUIDES, documents, lengths):
        score = 0.0
        for term in sorted(query_terms):
            frequency = document.get(term, 0)
            if not frequency:
                continue
            containing = frequencies[term]
            inverse_frequency = math.log(
                1.0 + (document_count - containing + 0.5) / (containing + 0.5)
            )
            normalisation = 1.5 * (
                0.25 + 0.75 * length / max(average_length, 1)
            )
            score += inverse_frequency * (
                frequency * 2.5 / (frequency + normalisation)
            )
        if score <= 0:
            continue
        exact = query.lower() in (guide['id'], guide['title'].lower())
        hit = {key: guide[key] for key in ('id', 'title', 'summary')}
        ranked.append((exact, score, guide['id'], hit))

    ranked.sort(key=lambda item: (-int(item[0]), -item[1], item[2]))
    return [item[3] for item in ranked[:MAX_RESULTS]]


def search_text(query, hits):
    """Render bounded summaries rather than dumping matching guide bodies."""
    lines = ['FORGE DOCS SEARCH: ' + query, '']
    if not hits:
        lines.extend([
            'No matching guides. Try a task word such as inspect, edit or recover.',
            'Browse all guides: FORGE docs',
        ])
    for hit in hits:
        lines.extend([
            hit['title'],
            '  ' + hit['summary'],
            '  -> FORGE docs ' + hit['id'],
            '',
        ])
    return '\n'.join(lines).rstrip()