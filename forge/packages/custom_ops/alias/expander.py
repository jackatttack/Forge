# -*- coding: utf-8 -*-
"""
Compatibility wrapper for alias expansion.

Alias expansion is owned by forge.core.preparse. This module remains only so
older references to the custom-op-local expander continue to resolve.
"""

from forge.core.preparse import (
    alias_entry_parts as _entry_parts,
    alias_info_bundle as _info_bundle,
    aliases_path as _aliases_path,
    known_op_names as _known_op_names,
    load_aliases as _load_aliases,
    substitute_alias_args as _substitute,
    try_expand_alias,
)