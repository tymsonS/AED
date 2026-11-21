"""Adaptery źródeł danych AED."""

from .danegovpl import DaneGovPlAdapter
from .dystrybutor import DystrybutorAdapter
from .openaedmap import OpenAedMapAdapter
from .wzorcowy_csv import WzorcowyCsvAdapter

ADAPTERS = {"danegovpl": DaneGovPlAdapter, "dystrybutor": DystrybutorAdapter, "openaedmap": OpenAedMapAdapter,
            "wzorcowy-csv": WzorcowyCsvAdapter}
# Źródła lokalne – fetch ich nie pobiera.
LOCAL_ADAPTERS = frozenset({"dystrybutor", "wzorcowy-csv"})
