"""Adaptery źródeł danych AED."""

from .danegovpl import DaneGovPlAdapter
from .openaedmap import OpenAedMapAdapter

ADAPTERS = {"danegovpl": DaneGovPlAdapter, "openaedmap": OpenAedMapAdapter}
