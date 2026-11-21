import pytest
from pytest_bdd import scenarios

from mcod.datasets.models import Dataset

# All tests in this module depend on component
pytestmark = [pytest.mark.depends_on_component, pytest.mark.component_api]

scenarios(
    "features/account.feature",
    "features/change_password.feature",
    "features/login.feature",
    "features/logout.feature",
    "features/resend_activation_email.feature",
    "features/reset_password_confirm.feature",
    "features/dashboard.feature",
    "features/meetings_api.feature",
    "features/dashboard_schedules.feature",
)


@pytest.mark.parametrize("client_version", ["client14_logged_user", "client_logged_user"])
def test_user_dashboard_request_returns_like_info(request, client_version: str, dataset_with_resources: Dataset):

    client = request.getfixturevalue(client_version)
    resp = client.simulate_post(f"/datasets/{dataset_with_resources.id}/likes")

    assert resp.status_code == 200
    assert resp.json["data"]["attributes"]["likes_count"] == 1

    resp = client.simulate_get("/auth/user/dashboard/")

    assert resp.status_code == 200
    assert resp.json["meta"]["aggregations"]["likes"]["likes_count"] == 1


@pytest.mark.parametrize("client_version", ["client14_logged_user", "client_logged_user"])
def test_user_dashboard_liked_list_returns_correct_datasets(
    request, client_version: str, dataset_with_resources: Dataset, dataset_with_resource_with_special_signs: Dataset
):
    # GIVEN
    client = request.getfixturevalue(client_version)
    client.simulate_post(f"/datasets/{dataset_with_resources.id}/likes")
    client.simulate_post(f"/datasets/{dataset_with_resource_with_special_signs.id}/likes")

    # WHEN
    resp = client.simulate_get("/auth/user/likes")

    # THEN
    assert resp.status_code == 200
    assert len(resp.json["data"]) == 2
    assert resp.json["data"][0]["type"] == "dataset"
    assert resp.json["data"][1]["type"] == "dataset"
    assert set(item["id"] for item in resp.json["data"]) == {
        str(dataset_with_resources.id),
        str(dataset_with_resource_with_special_signs.id),
    }
