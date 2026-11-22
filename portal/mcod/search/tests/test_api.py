import pytest
from pytest_bdd import scenarios

from mcod.core.tests.helpers.tasks import run_on_commit_events
from mcod.datasets.models import Dataset

# All tests in this module depend on component
pytestmark = [pytest.mark.depends_on_component, pytest.mark.component_api]

scenarios(
    "features/search.feature",
    "features/sparql.feature",
    "features/suggest.feature",
    "features/other_sparql_endpoints.feature",
)


@pytest.mark.elasticsearch
@pytest.mark.parametrize("client_version", ["client14_logged_user", "client_logged_user"])
def test_dataset_likes_in_search_view(request, client_version: str, dataset_with_run_events: Dataset):
    # GIVEN
    client = request.getfixturevalue(client_version)

    # WHEN
    resp = client.simulate_get("/search?model[terms]=dataset")

    # THEN
    assert "likes_count" in resp.json["data"][0]["attributes"]
    assert "is_liked_by_current_user" in resp.json["data"][0]["attributes"]
    assert resp.json["data"][0]["attributes"]["likes_count"] == 0
    assert resp.json["data"][0]["attributes"]["is_liked_by_current_user"] is False

    # WHEN
    client.simulate_post(f"/datasets/{dataset_with_run_events.id}/likes")
    run_on_commit_events()
    resp = client.simulate_get("/search?model[terms]=dataset")

    # THEN
    assert resp.json["data"][0]["attributes"]["likes_count"] == 1
    assert resp.json["data"][0]["attributes"]["is_liked_by_current_user"] is True
