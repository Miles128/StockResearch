"""Reusable agent-stream orchestration primitives."""

from stockresearch.agents.framework.pipeline import (
    DebateConfig,
    DimensionJob,
    stream_debate_pipeline,
    stream_dimension_jobs,
)

__all__ = [
    "DebateConfig",
    "DimensionJob",
    "stream_dimension_jobs",
    "stream_debate_pipeline",
]
