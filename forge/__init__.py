# -*- coding: utf-8 -*-
"""
Portable Forge public Python API.

Normal use:

    import forge

    run = forge.run_text(
        bundle,
        project_root='/path/to/project',
    )

    print(
        forge.render_standard(run)
    )

Advanced callers may build and supply an explicit environment.
"""

from forge.core.environment import make_environment
from forge.core.presentation.standard import (
    format_summary,
    render_standard,
)

from .standard import (
    bundle_syntax_text,
    default_forge_home,
    first_boot_text,
    main,
    run_text,
    standard_environment,
)


__all__ = [
    'bundle_syntax_text',
    'default_forge_home',
    'first_boot_text',
    'format_summary',
    'main',
    'make_environment',
    'render_standard',
    'run_text',
    'standard_environment',
]