import zipfile
from pathlib import Path

import pytest
from django.test import override_settings
from django.utils.translation import gettext_lazy as _
from falcon import HTTP_OK
from pytest_bdd import scenarios

from mcod.core.tests.helpers.tasks import run_on_commit_events
from mcod.datasets.factories import DatasetFactory
from mcod.datasets.models import Dataset
from mcod.datasets.serializers import _UPDATE_FREQUENCY
from mcod.resources.factories import ResourceFactory

# All tests in this module depend on component
pytestmark = [pytest.mark.depends_on_component, pytest.mark.component_api]

scenarios(
    "features/dataset_comment.feature",
    "features/dataset_resources_list_api.feature",
    "features/dataset_details_api.feature",
    "features/dataset_resources_download_csv_api.feature",
    "features/dataset_resources_download_xml_api.feature",
    "features/dataset_licenses.feature",
    "features/dataset_showcases_list_api.feature",
    "features/dataset_bulk_download_files_api.feature",
    "features/datasets_list_api.feature",
)

scenarios("features/dataset_unified_conditions.feature")


def test_post_likes_registers_and_increments_counter(client14_logged_user, client14_logged_admin, dataset_with_resources):
    resp = client14_logged_user.simulate_post(f"/datasets/{dataset_with_resources.id}/likes")
    assert resp.status_code == 200
    assert resp.json["data"]["attributes"]["likes_count"] == 1

    resp = client14_logged_admin.simulate_post(f"/datasets/{dataset_with_resources.id}/likes")

    assert resp.status_code == 200
    assert resp.json["data"]["attributes"]["likes_count"] == 2


def test_likes_without_token_401(client14, dataset_with_resources):
    resp = client14.simulate_post(f"/datasets/{dataset_with_resources.id}/likes")

    assert resp.status_code == 401

    resp = client14.simulate_delete(f"/datasets/{dataset_with_resources.id}/likes")

    assert resp.status_code == 401


def test_likes_nonexistent_returns_404(client14_logged_user):
    resp = client14_logged_user.simulate_post("/datasets/999/likes")

    assert resp.status_code == 404

    resp = client14_logged_user.simulate_delete("/datasets/999/likes")

    assert resp.status_code == 404


def test_likes_double_like_operation_does_not_succeed(client14_logged_user, dataset_with_resources):
    client14_logged_user.simulate_post(f"/datasets/{dataset_with_resources.id}/likes")
    resp = client14_logged_user.simulate_post(f"/datasets/{dataset_with_resources.id}/likes")

    assert resp.status_code == 409
    assert resp.json["errors"][0]["detail"] == "Ten zbiór jest już w Twoich ulubionych."

    client14_logged_user.simulate_delete(f"/datasets/{dataset_with_resources.id}/likes")
    resp = client14_logged_user.simulate_delete(f"/datasets/{dataset_with_resources.id}/likes")

    assert resp.status_code == 409
    assert resp.json["errors"][0]["detail"] == "Ten zbiór został już usunięty z listy ulubionych."


@pytest.mark.parametrize("client_version", ["client14_logged_user", "client_logged_user"])
def test_delete_likes_remove_existing_like(request, client_version: str, dataset_with_resources):

    client = request.getfixturevalue(client_version)
    resp = client.simulate_post(f"/datasets/{dataset_with_resources.id}/likes")

    assert resp.status_code == 200
    assert resp.json["data"]["attributes"]["likes_count"] == 1

    resp = client.simulate_delete(f"/datasets/{dataset_with_resources.id}/likes")

    assert resp.status_code == 200
    assert resp.json["data"]["attributes"]["likes_count"] == 0


@pytest.mark.elasticsearch
def test_dates_in_list_views_api14(dataset_with_run_events, client14):
    resp = client14.simulate_get("/datasets")
    assert HTTP_OK == resp.status
    assert dataset_with_run_events.id
    for d_name in ["created", "modified", "verified"]:
        assert d_name in resp.json["data"][0]["attributes"]


@pytest.mark.elasticsearch
@pytest.mark.parametrize("client_version", ["client14_logged_user", "client_logged_user"])
def test_likes_data_in_list_views(request, client_version: str, dataset_with_run_events: Dataset):
    # GIVEN
    client = request.getfixturevalue(client_version)

    # WHEN
    resp = client.simulate_get("/datasets")

    # THEN
    assert "likes_count" in resp.json["data"][0]["attributes"]
    assert "is_liked_by_current_user" in resp.json["data"][0]["attributes"]
    assert resp.json["data"][0]["attributes"]["likes_count"] == 0
    assert resp.json["data"][0]["attributes"]["is_liked_by_current_user"] is False

    # WHEN
    client.simulate_post(f"/datasets/{dataset_with_run_events.id}/likes")
    run_on_commit_events()
    resp = client.simulate_get("/datasets")

    # THEN
    assert resp.json["data"][0]["attributes"]["likes_count"] == 1
    assert resp.json["data"][0]["attributes"]["is_liked_by_current_user"] is True


@pytest.mark.parametrize("client_version", ["client14_logged_user", "client_logged_user"])
def test_likes_data_in_detail_view(request, client_version: str, dataset_with_resources):
    client = request.getfixturevalue(client_version)

    resp = client.simulate_get(f"/datasets/{dataset_with_resources.id}")

    assert "likes_count" in resp.json["data"]["attributes"]
    assert "is_liked_by_current_user" in resp.json["data"]["attributes"]
    assert resp.json["data"]["attributes"]["likes_count"] == 0
    assert resp.json["data"]["attributes"]["is_liked_by_current_user"] is False

    client.simulate_post(f"/datasets/{dataset_with_resources.id}/likes")
    resp = client.simulate_get(f"/datasets/{dataset_with_resources.id}")

    assert resp.json["data"]["attributes"]["likes_count"] == 1
    assert resp.json["data"]["attributes"]["is_liked_by_current_user"] is True


@pytest.mark.elasticsearch
@pytest.mark.parametrize("client_version", ["client14_logged_user", "client_logged_user"])
def test_datasets_likes_sorting_with_date_tiebreaker(request, client_version: str):
    client = request.getfixturevalue(client_version)

    older = DatasetFactory(status="published")
    newer = DatasetFactory(status="published")

    resp = client.simulate_post(f"/datasets/{older.id}/likes")
    assert resp.status_code == 200

    run_on_commit_events()

    resp = client.simulate_get("/search?sort=-likes_count&model[terms]=dataset")
    assert resp.status_code == 200
    ids_by_result_order = [item["id"] for item in resp.json["data"]]
    assert ids_by_result_order.index(str(older.id)) < ids_by_result_order.index(str(newer.id))

    resp = client.simulate_post(f"/datasets/{newer.id}/likes")
    assert resp.status_code == 200

    first_resource = ResourceFactory()
    second_resource = ResourceFactory()
    run_on_commit_events()

    resp = client.simulate_get("/search?sort=-likes_count&model[terms]=dataset")
    assert resp.status_code == 200
    ids_by_result_order = [item["id"] for item in resp.json["data"]]
    assert ids_by_result_order.index(str(newer.id)) < ids_by_result_order.index(str(older.id))

    resp = client.simulate_get("/search?sort=-likes_count&model[terms]=dataset,resource")
    assert resp.status_code == 200
    items = [(item["attributes"]["model"], item["id"]) for item in resp.json["data"]]
    assert items.index(("dataset", str(older.id))) < items.index(("resource", str(second_resource.id)))
    assert items.index(("dataset", str(newer.id))) < items.index(("resource", str(second_resource.id)))
    assert items.index(("resource", str(second_resource.id))) < items.index(("resource", str(first_resource.id)))


@pytest.mark.elasticsearch
def test_dates_in_detail_views_api14(dataset, client14):
    _rid = dataset.id
    resp = client14.simulate_get("/datasets/{}/".format(_rid))
    assert HTTP_OK == resp.status
    for d_name in ["created", "modified", "verified"]:
        assert d_name in resp.json["data"]["attributes"]

    assert resp.json["data"]["attributes"]["modified"] == dataset.modified.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["created"] == dataset.created.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["verified"] == dataset.created.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.elasticsearch
def test_data_date_with_resource_views_api14(dataset_with_resources, client14):
    dataset = dataset_with_resources
    resource = dataset.resources.first()
    id_ = dataset.id
    resource.revalidate()
    assert set(dataset.types) == set([r.type for r in dataset.resources.all()])

    resp = client14.simulate_get("/datasets/{}/".format(id_))
    assert HTTP_OK == resp.status
    for d_name in ["created", "modified", "verified"]:
        assert d_name in resp.json["data"]["attributes"]

    assert resp.json["data"]["attributes"]["modified"] == dataset.modified.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["created"] == dataset.created.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["verified"] == dataset.resources.last().created.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.elasticsearch
def test_dates_in_list_views_api14_in_path(dataset, resource, client14):
    resp = client14.simulate_get("/1.4/datasets/")
    assert HTTP_OK == resp.status
    assert dataset.id
    for d_name in ["created", "modified", "verified"]:
        assert d_name in resp.json["data"][0]["attributes"]


@pytest.mark.elasticsearch
def test_dates_in_detail_views_api14_in_path(dataset, client14):
    _rid = dataset.id
    resp = client14.simulate_get("/1.4/datasets/{}/".format(_rid))
    assert HTTP_OK == resp.status
    for d_name in ["created", "modified", "verified"]:
        assert d_name in resp.json["data"]["attributes"]

    assert resp.json["data"]["attributes"]["modified"] == dataset.modified.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["created"] == dataset.created.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["verified"] == dataset.verified.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json.get("jsonapi")


@pytest.mark.elasticsearch
def test_datasets_dates_in_list_views(dataset_with_run_events, client):
    resp = client.simulate_get("/datasets/")
    assert HTTP_OK == resp.status
    for d_name in ["created", "modified", "verified"]:
        assert d_name in resp.json["data"][0]["attributes"]


@pytest.mark.elasticsearch
def test_dataset_dates_in_detail_views(dataset, resource, client):
    _id = dataset.id
    resource.revalidate()
    resp = client.simulate_get("/datasets/{}/".format(_id))

    assert HTTP_OK == resp.status
    for d_name in ["created", "modified", "verified"]:
        assert d_name in resp.json["data"]["attributes"]

    ds = Dataset.objects.get(pk=dataset.id)
    assert resp.json["data"]["attributes"]["modified"] == dataset.modified.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["created"] == dataset.created.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["verified"] == ds.verified.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.elasticsearch
def test_datasets_dates_in_list_views_api_1_0_in_path(dataset_with_run_events, client):
    resp = client.simulate_get("/1.0/datasets/")
    assert HTTP_OK == resp.status
    for d_name in ["created", "modified", "verified"]:
        assert d_name in resp.json["data"][0]["attributes"]


@pytest.mark.elasticsearch
def test_dataset_dates_in_detail_views_api_1_0_in_path(dataset, resource, client):
    _id = dataset.id
    resource.revalidate()
    resp = client.simulate_get("/1.0/datasets/{}/".format(_id))

    assert HTTP_OK == resp.status
    for d_name in ["created", "modified", "verified"]:
        assert d_name in resp.json["data"]["attributes"]

    ds = Dataset.objects.get(pk=dataset.id)
    assert resp.json["data"]["attributes"]["modified"] == dataset.modified.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["created"] == dataset.created.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert resp.json["data"]["attributes"]["verified"] == ds.verified.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.elasticsearch
def test_dataset_update_frequency_in_detail_views_api_1_0(dataset, client):
    resp = client.simulate_get("/1.0/datasets/{}/".format(dataset.id))
    assert HTTP_OK == resp.status
    assert resp.json["data"]["attributes"]["update_frequency"] == _(_UPDATE_FREQUENCY[dataset.update_frequency])


@pytest.mark.elasticsearch
def test_dataset_update_frequency_in_detail_views_api_1_4(dataset, client):
    resp = client.simulate_get("/1.4/datasets/{}/".format(dataset.id))
    assert HTTP_OK == resp.status
    assert resp.json["data"]["attributes"]["update_frequency"] == _(_UPDATE_FREQUENCY[dataset.update_frequency])


@pytest.mark.elasticsearch
def test_slug_in_organization_link_datasets_list(dataset_with_run_events, client):
    resp = client.simulate_get("/1.4/datasets/")
    assert HTTP_OK == resp.status
    assert resp.json["data"][0]["relationships"]["institution"]["links"]["related"].endswith(
        f"{dataset_with_run_events.institution.id},{dataset_with_run_events.institution.slug}"
    )


@pytest.mark.elasticsearch
def test_slug_in_organization_link_dataset_details(dataset, client):
    resp = client.simulate_get(f"/1.4/datasets/{dataset.id}")
    assert HTTP_OK == resp.status
    assert resp.json["data"]["relationships"]["institution"]["links"]["related"].endswith(
        f"{dataset.institution.id},{dataset.institution.slug}"
    )


@pytest.mark.elasticsearch
def test_datasets_routes(dataset, client):
    paths = [
        "/1.4/datasets",
        f"/1.4/datasets/{dataset.id}",
        f"/1.4/datasets/{dataset.id},{dataset.slug}",
        f"/1.4/datasets/{dataset.id}/resources",
        f"/1.4/datasets/{dataset.id},{dataset.slug}/resources",
    ]

    for p in paths:
        resp = client.simulate_get(p)
        assert resp.status == HTTP_OK


@pytest.mark.elasticsearch
def test_response_datasets_list_slug_in_link(dataset_with_run_events, client14):
    resp = client14.simulate_get("/datasets/")
    assert HTTP_OK == resp.status
    assert f"{dataset_with_run_events.id},{dataset_with_run_events.slug}" in resp.json["data"][0]["links"]["self"]


@pytest.mark.elasticsearch
def test_response_dataset_details_slug_in_link(dataset, client14):
    resp = client14.simulate_get(f"/datasets/{dataset.id}")
    assert HTTP_OK == resp.status
    assert f"{dataset.id},{dataset.slug}" in resp.json["data"]["links"]["self"]


@pytest.mark.elasticsearch
def test_response_dataset_image_uri_in_details(dataset, client, small_image):
    dataset.image = small_image
    dataset.save()
    resp = client.simulate_get("/1.4/datasets/{}/".format(dataset.id))
    assert HTTP_OK == resp.status
    assert resp.json["data"]["attributes"]["image_url"] == f"/media/images/datasets/{dataset.image.name}"


@pytest.mark.parametrize("language", ("en", "pl"))
def test_zip_catalog_download(client14, tmp_path: str, language: str):
    with override_settings(METADATA_MEDIA_ROOT=tmp_path):
        # GIVEN
        # Create zip file with dummy data
        catalog_dest = Path(tmp_path) / language
        catalog_dest.mkdir(exist_ok=True, parents=True)
        zip_file_path = catalog_dest / "katalog.zip"
        dummy_content = b"dummy file data"
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("dummy_data.txt", dummy_content)

        # Read the exact bytes of the generated zip to compare with the response
        expected_zip_data = zip_file_path.read_bytes()

        # WHEN Perform the request
        response = client14.simulate_get(f"/datasets/resources/metadata.zip?lang={language}")

        # THEN
        assert response.status == HTTP_OK
        content_type = response.headers.get("Content-Type", "")
        assert content_type == "application/zip"
        assert response.content == expected_zip_data
