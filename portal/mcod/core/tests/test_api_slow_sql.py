import json
import logging

import pytest
from django.test import override_settings
from falcon import testing


@pytest.mark.django_db
@pytest.mark.usefixtures(
    "api_with_routes_for_test",
    "slow_sql_log_propagation",
)
@pytest.mark.parametrize(
    "threshold, should_log",
    [
        (1.5, False),
        (0.5, True),
    ],
)
def test_sql_query_logging_based_on_threshold(
    client: testing.TestClient,
    caplog: pytest.LogCaptureFixture,
    threshold: float,
    should_log: bool,
):
    with override_settings(
        SLOW_SQL_LOGGING_ENABLED=True,
        SLOW_SQL_THRESHOLD_SECONDS=threshold,
    ):
        response = client.simulate_get("/1.4/sql-query-endpoint")

    assert response.status_code == 200
    assert json.loads(response.text) == {"message": "OK"}

    records = [rec for rec in caplog.records if rec.name == "slow-sql" and rec.levelno == logging.WARNING]

    if should_log:
        assert len(records) == 1
        event = json.loads(records[0].getMessage())
        assert event["event_type"] == "slow_sql"
        assert event["operation"] == "GET /1.4/sql-query-endpoint"
        assert threshold < event["duration"] < 1.1
        assert event["sql"] == "SELECT pg_sleep(%s)"
        assert event["request_succeeded"] is True
        assert event["user_authenticated"] is False
        assert len(event["sql_hash"]) == 16
    else:
        assert records == []
