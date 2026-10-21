"""who-was-heard — 공론을 한데 모으되, 묻히는 목소리를 놓치지 않기 위한 도구.

Fair Listening (고루듣기). Tools for bringing public discourse together in the
YouTube era — without losing the voices that get drowned out.

이 도구는 AI 의견 지도를 얼마나 믿을 수 있는지까지만 말한다.
무엇을 뜻하는지는 말하지 않는다.
It tells you how far to trust an AI opinion map — not what it means.
"""

__version__ = "0.1.0"

from .data import load_table, columns  # noqa: F401
from .clean import CleanRules, clean  # noqa: F401
from .concentration import concentration  # noqa: F401
from .report import diagnose, write_reports  # noqa: F401
