from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from ..models import StudySearchResult
from ._base import Resource


class Studies(Resource):
    """The studies of the albums the caller sees (``/studies/``)."""

    def search(
        self,
        q: str,
        *,
        limit: int = 50,
        modalities: Iterable[str] | None = None,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ) -> StudySearchResult:
        """The studies matching ``q`` (at least 2 characters), at most ``limit`` (1–200).

        Every word of ``q`` must appear, case-insensitively, in the patient ID, the patient name, the study description or the
        accession number (``john doe`` matches ``DOE^JOHN``). ``modalities`` keeps the studies with a series of one of them;
        ``date_from`` and ``date_to`` bound the study date. ``has_more`` is true when more studies match: refine ``q``, the
        search is not paginated.
        """
        if isinstance(modalities, str):
            modalities = [modalities]
        data = self._get(
            'studies/',
            q=q,
            limit=limit,
            modality=list(modalities) if modalities is not None else None,
            date_from=date_from,
            date_to=date_to,
        )
        return StudySearchResult.model_validate(data)
