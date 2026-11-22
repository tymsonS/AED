import json
from unittest.mock import MagicMock

import pytest
from django.test import Client, override_settings
from pytest_mock import MockerFixture

from mcod.core.api.middlewares import QueryLogger, SlowSQLMiddleware


def test_user_token_middleware(admin, settings):
    client = Client()

    resp = client.get("/")
    assert resp.status_code == 302
    assert settings.API_TOKEN_COOKIE_NAME not in resp.cookies

    client.force_login(admin)
    resp = client.get("/")
    assert resp.status_code == 200
    assert settings.API_TOKEN_COOKIE_NAME in resp.cookies

    client.get("/logout/")
    resp = client.get("/")
    assert resp.status_code == 302
    assert settings.API_TOKEN_COOKIE_NAME in resp.cookies
    assert resp.cookies[settings.API_TOKEN_COOKIE_NAME]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"
    # cookie will be deleted


@pytest.mark.parametrize(
    ("method", "path", "duration", "should_log", "user_authenticated"),
    [
        ("GET", "/datasets/", 0.842, False, False),
        ("GET", "/datasets/", 1.0, False, False),
        ("GET", "/datasets/", 1.00001, True, False),
        ("POST", "/resources/", 2.84321, True, True),
    ],
)
@override_settings(
    SLOW_SQL_LOGGING_ENABLED=True,
    SLOW_SQL_THRESHOLD_SECONDS=1.0,
)
def test_slow_sql_middleware(
    method,
    path,
    duration,
    should_log,
    user_authenticated,
    mocker: MockerFixture,
):
    sample_sql = 'SELECT "dataset"."id" FROM "dataset"'

    ql = QueryLogger()
    ql.queries = [
        {
            "sql": sample_sql,
            "params": [],
            "many": False,
            "duration": duration,
        },
    ]

    req = MagicMock()
    req.method = method
    req.path = path
    req.user.is_authenticated = user_authenticated
    req.context = {SlowSQLMiddleware.SLOW_SQL_LOGGER_CONTEXT_KEY: ql}

    mock_warning = mocker.patch("mcod.core.api.middlewares.slow_sql_logger.warning")
    mock_execute_wrappers = mocker.patch("mcod.core.api.middlewares.connection.execute_wrappers")

    SlowSQLMiddleware().process_response(req, MagicMock(), None, True)

    if should_log:
        mock_warning.assert_called_once()
        event = json.loads(mock_warning.call_args.args[0])
        assert event["event_type"] == "slow_sql"
        assert event["duration"] == round(duration, 3)
        assert event["operation"] == f"{method} {path}"
        assert event["sql"] == sample_sql
        assert event["request_succeeded"] is True
        assert event["user_authenticated"] is user_authenticated
        assert len(event["sql_hash"]) == 16
    else:
        mock_warning.assert_not_called()

    mock_execute_wrappers.remove.assert_called_once_with(ql)


@override_settings(SLOW_SQL_LOGGING_ENABLED=False)
def test_slow_sql_middleware_disabled(mocker: MockerFixture):
    req = MagicMock()
    req.context = {}

    mock_execute_wrappers = mocker.patch("mcod.core.api.middlewares.connection.execute_wrappers")

    SlowSQLMiddleware().process_request(req, MagicMock())

    assert SlowSQLMiddleware.SLOW_SQL_LOGGER_CONTEXT_KEY not in req.context
    mock_execute_wrappers.append.assert_not_called()
