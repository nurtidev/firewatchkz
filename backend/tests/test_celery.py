import pytest
from unittest.mock import patch, MagicMock


def test_celery_app_imports():
    from celery_app import celery_app
    assert celery_app.main == "firewatch"


def test_task_names_registered():
    from celery_app import celery_app
    # Tasks are registered after import
    import workers.documents  # noqa
    registered = list(celery_app.tasks.keys())
    assert "workers.documents.normalize_document" in registered
    assert "workers.documents.extract_document" in registered
    assert "workers.documents.analyze_vulnerabilities" in registered


def test_task_routing():
    from celery_app import celery_app
    routes = celery_app.conf.task_routes
    assert "workers.documents.*" in routes
    assert routes["workers.documents.*"]["queue"] == "documents"


def test_normalize_document_task_signature():
    from workers.documents import normalize_document

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = None  # card not found → early return
    mock_conn.cursor.return_value = mock_cursor

    with patch("workers.documents._sync_db_conn", return_value=mock_conn):
        result = normalize_document.apply(args=["test-card-id"])

    assert result.result["card_id"] == "test-card-id"
    assert "status" in result.result
