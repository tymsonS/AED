"""Adaptery źródeł danych AED."""

from .danegovpl import DaneGovPlAdapter
from .dystrybutor import DystrybutorAdapter
from .openaedmap import OpenAedMapAdapter

ADAPTERS = {"danegovpl": DaneGovPlAdapter, "dystrybutor": DystrybutorAdapter, "openaedmap": OpenAedMapAdapter}
