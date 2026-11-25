"""What Anvil's Help page shows: Forge's operations, its workflow docs, the
bundle grammar and the workspace's guides.

Role: gather · Part of: anvil/help · Pure

Pure Python, no ui. Everything is read in-process from the Forge that is
running (its op registry, its docs package, the FORGE op's own text), so
Help always matches the installed Forge. Every reader returns [] or None
when Forge or a folder is missing: Help shows what it can and never stops a
run from showing.

    ops()                         -> [OpHelp]: public ops in FORGE ops' order,
                                     then local extensions A to Z
    op_help(name)                 -> OpHelp with its README, or None
    docs()                        -> [Doc]: Forge's guides and the bundle grammar
    guides(workspace)             -> [Doc]: library/guides/*.md
    find_doc(kind, name, workspace) -> Doc or None
    doc_text(doc)                 -> the doc's whole text
"""
import os


# --- Settings ---------------------------------------------------------------

GUIDES_FOLDER = os.path.join('library', 'guides')
GUIDE_HEAD_LINES = 8               # lines read for a guide's title and "Use when:"
BUNDLE_DOC = 'bundle'              # Help's name for FORGE bundle's grammar
BUNDLE_TITLE = 'Bundle grammar'
BUNDLE_WORDS = ('How a bundle is written: ops, directives, bodies and tagged '
                'blocks. The first stop after FAILED_PARSE.')
LOAD_FAILED = 'This page did not load: '


# --- Records ----------------------------------------------------------------

class OpHelp(object):
    """One operation's help, as Forge's registry holds it."""

    def __init__(self, name, public):
        self.name = name
        self.public = public       # listed by FORGE ops; else a local extension
        self.summary = ''
        self.brief = ''            # the hand-written line under FORGE ops' summary
        self.directives = []       # [(DIRECTIVE, what it does)], A to Z
        self.example = []          # HELP['minimal_example'] lines
        self.target = ''           # SPEC target_kind
        self.body = ''             # SPEC body_mode
        self.readme = ''           # README.txt; op_help() reads it


class Doc(object):
    """A page of words: a Forge doc (kind 'forge') or a guide ('guide')."""

    def __init__(self, kind, name, title, words='', path=''):
        self.kind = kind
        self.name = name
        self.title = title
        self.words = words         # one line: what it covers, when to read it
        self.path = path           # guides only


# --- Operations -------------------------------------------------------------

def forge_registry():
    """(Forge's ops by name, public op names in order); ({}, []) without Forge."""
    try:
        from forge.core.registry import OPS_BY_NAME, discover_ops
        from forge.core.language import public_ops
        discover_ops()
        return OPS_BY_NAME, [str(name) for name in public_ops()]
    except Exception:
        return {}, []


def as_lines(value):
    if isinstance(value, str):
        return value.splitlines()
    return [str(line) for line in (value or [])]


def describe(name, module, public):
    """An OpHelp from the op module's HELP and SPEC (no README)."""
    op = OpHelp(name, public)
    help_data = getattr(module, 'HELP', None) or {}
    spec = getattr(module, 'SPEC', None) or {}
    op.summary = str(help_data.get('summary') or '').strip()
    op.brief = str(help_data.get('brief') or '').strip()
    op.example = as_lines(help_data.get('minimal_example'))
    op.target = str(spec.get('target_kind') or '')
    op.body = str(spec.get('body_mode') or '')
    documented = help_data.get('directives')
    if isinstance(documented, dict):
        op.directives = sorted((str(key).upper(), str(value or '').strip())
                               for key, value in documented.items())
    else:                          # undocumented: what the parser accepts, minus plumbing
        internal = set(str(value).upper() for value in (help_data.get('internal_directives') or []))
        accepted = set(str(value).upper() for value in (spec.get('allowed_directives') or []))
        op.directives = [(key, '') for key in sorted(accepted - internal)]
    return op


def ops():
    registered, public = forge_registry()
    names = [name for name in public if name in registered]
    names += sorted(name for name in registered if name not in names)
    return [describe(name, registered[name], name in public) for name in names]


def op_help(name):
    registered, public = forge_registry()
    name = str(name or '').strip().upper()
    module = registered.get(name)
    if module is None:
        return None
    op = describe(name, module, name in public)
    op.readme = readme_for(name)
    return op


def readme_for(name):
    """The op package's README.txt: from its folder, else through the FORGE
    op's own reader (packaged resources). '' when there is none."""
    folder = ''
    try:
        from forge.core.registry import get_package_path
        folder = get_package_path(name) or ''
    except Exception:
        pass
    path = os.path.join(folder, 'README.txt') if folder else ''
    if path and os.path.isfile(path):
        return read_text(path)
    try:
        from forge.packages.core_ops.forge import op as forge_op
        return forge_op._read_package_text(name, folder, 'README.txt') or ''
    except Exception:
        return ''


# --- Docs and guides --------------------------------------------------------

def first_text(entry, keys):
    for key in keys:
        value = str(entry.get(key) or '').strip()
        if value:
            return value
    return ''


def bundle_syntax_text():
    """FORGE bundle's text, or None when this Forge cannot give it."""
    from forge.packages.core_ops.forge import op as forge_op
    result = {}
    forge_op._bundle_syntax(result)
    return str(result.get('preview') or '') or None


def docs():
    found = []
    try:
        from forge import docs as forge_docs
        for entry in forge_docs.catalogue():
            if not isinstance(entry, dict):
                continue
            name = first_text(entry, ('name', 'slug', 'id'))
            if name:
                found.append(Doc('forge', name, first_text(entry, ('title',)) or name,
                                 first_text(entry, ('summary', 'use_when', 'description', 'purpose'))))
    except Exception:
        pass
    try:
        if bundle_syntax_text():
            found.append(Doc('forge', BUNDLE_DOC, BUNDLE_TITLE, BUNDLE_WORDS))
    except Exception:
        pass
    return found


def guide_heading(path):
    """(title, use when) from a guide's first lines; blanks when missing."""
    title, words = '', ''
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            for _ in range(GUIDE_HEAD_LINES):
                stripped = handle.readline().strip()
                if stripped.startswith('# ') and not title:
                    title = stripped[2:].strip()
                elif stripped.lower().startswith('use when:'):
                    words = stripped.split(':', 1)[1].strip()
    except Exception:
        pass
    return title, words


def guides(workspace):
    folder = os.path.join(workspace or '', GUIDES_FOLDER)
    if not workspace or not os.path.isdir(folder):
        return []
    found = []
    for file_name in sorted(os.listdir(folder)):
        if file_name.startswith('.') or not file_name.endswith('.md'):
            continue
        if file_name.lower() == 'readme.md':
            continue
        path = os.path.join(folder, file_name)
        title, words = guide_heading(path)
        slug = file_name[:-3]
        found.append(Doc('guide', slug, title or slug, words, path))
    return found


def find_doc(kind, name, workspace):
    for doc in docs() + guides(workspace):
        if doc.kind == kind and doc.name == name:
            return doc
    return None


def doc_text(doc):
    """The doc's whole text. A doc that will not load says so instead."""
    try:
        if doc.kind == 'guide':
            return read_text(doc.path)
        if doc.name == BUNDLE_DOC:
            return bundle_syntax_text() or ''
        from forge import docs as forge_docs
        return str(forge_docs.read_guide(doc.name) or '')
    except Exception as error:
        return LOAD_FAILED + str(error)


def read_text(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return handle.read()