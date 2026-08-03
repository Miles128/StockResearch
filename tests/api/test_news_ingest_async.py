"""News ingest should return immediately and run in the background."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_ingest_returns_accepted_job(client: TestClient) -> None:
    async def _ingest(*_args, **_kwargs):
        from stockresearch.data.pipeline.news import NewsIngestResult

        return NewsIngestResult(inserted=1, scanned=2, skipped=0, message="ok")

    with patch("stockresearch.services.news_ingest_jobs.NewsPipeline") as pipeline_cls:
        pipeline_cls.return_value.ingest = AsyncMock(side_effect=_ingest)
        with patch("stockresearch.services.news_ingest_jobs.purge_irrelevant_news", return_value=0):
            resp = client.post("/api/v1/news/ingest?limit=5")

    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "queued"


def test_ingest_job_status_completes(client: TestClient) -> None:
    async def _fast_ingest(*_args, **_kwargs):
        from stockresearch.data.pipeline.news import NewsIngestResult

        return NewsIngestResult(inserted=2, scanned=3, skipped=1, message="done")

    with patch("stockresearch.services.news_ingest_jobs.NewsPipeline") as pipeline_cls:
        pipeline_cls.return_value.ingest = AsyncMock(side_effect=_fast_ingest)
        with patch("stockresearch.services.news_ingest_jobs.purge_irrelevant_news", return_value=4):
            create = client.post("/api/v1/news/ingest?limit=5")
            assert create.status_code == 202
            job_id = create.json()["job_id"]

            # TestClient runs BackgroundTasks before returning, so job should be done.
            status = client.get(f"/api/v1/news/ingest/{job_id}")
            assert status.status_code == 200
            body = status.json()
            assert body["status"] == "completed"
            assert body["inserted"] == 2
            assert body["scanned"] == 3
            assert body["skipped"] == 1
            assert body["purged"] == 4
            assert "done" in body["message"]


def test_ingest_job_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/news/ingest/missing-job-id")
    assert resp.status_code == 404
