from pathlib import Path

import factory
import openpyxl
import pytest
from pytest_bdd import scenarios

from mcod.core.tests.helpers.tasks import run_on_commit_events
from mcod.resources.factories import ResourceXlsxFactory
from mcod.resources.models import Resource

scenarios(
    "features/task_results.feature",
)


@pytest.mark.elasticsearch
def test_headers_only_csv_file_validation(onlyheaderscsv_resource):
    run_on_commit_events()
    assert onlyheaderscsv_resource.data_tasks.count() == 1
    assert "zero-data-rows" in onlyheaderscsv_resource.data_tasks.order_by("id").last().result
    onlyheaderscsv_resource.revalidate()
    run_on_commit_events()
    assert onlyheaderscsv_resource.data_tasks.count() == 2
    assert "zero-data-rows" in onlyheaderscsv_resource.data_tasks.order_by("id").last().result


@pytest.mark.elasticsearch
def test_xlsx_file_with_empty_cells_validation_success(tmp_path: Path) -> None:
    # GIVEN
    file_path: Path = tmp_path / "test_empty_cells.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["id", "name", "optional_col_1", "optional_col_2", "optional_col_3"])
    sheet.append([1, "Item 1", None, "Value 1", None])
    sheet.append([2, "Item 2", "Value 2", None, None])
    workbook.save(filename=str(file_path))

    # WHEN
    resource: Resource = ResourceXlsxFactory.create(
        status="published",
        main_file__file=factory.django.FileField(
            from_path=str(file_path),
            filename="test_empty_cells.xlsx",
        ),
    )
    run_on_commit_events()

    # THEN
    resource.refresh_from_db()
    assert resource.data_tasks_last_status == "SUCCESS"
    assert resource.file_tasks_last_status == "SUCCESS"
    assert resource.link_tasks_last_status == "SUCCESS"
