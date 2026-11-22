import pytest

from mcod.core.tests.helpers.tasks import run_on_commit_events
from mcod.datasets.documents import DatasetDocument
from mcod.datasets.factories import DatasetFactory
from mcod.users.models import User


@pytest.mark.elasticsearch
def test_dataset_document_reindex_after_like_change(admin: User, active_user: User):
    # GIVEN
    dataset = DatasetFactory.create()
    # WHEN
    dataset.add_like(active_user)
    dataset.add_like(admin)
    run_on_commit_events()
    doc = DatasetDocument.get(id=dataset.pk)
    # THEN
    assert doc.likes_count == 2
    assert set(doc.liked_by) == {active_user.pk, admin.pk}
    # AND WHEN
    dataset.remove_like(active_user)
    run_on_commit_events()
    doc = DatasetDocument.get(id=dataset.pk)
    # THEN
    assert doc.likes_count == 1
    assert set(doc.liked_by) == {admin.pk}
