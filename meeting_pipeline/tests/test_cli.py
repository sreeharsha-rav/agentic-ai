from __future__ import annotations

import json

import pytest

from meeting_pipeline.cli import _parse_stages, build_parser, config_from_args, main
from meeting_pipeline.config import PipelineConfig
from meeting_pipeline.pipeline import Stage


def test_build_parser_run_basic():
    parser = build_parser()
    args = parser.parse_args(["run", "--video", "a.mp4", "--out", "o", "--stages", "context,align"])
    assert args.command == "run"
    assert args.video == "a.mp4"
    assert args.output_dir == "o"
    assert args.stages == "context,align"
    assert args.resume is False


def test_missing_required_video_raises_system_exit_2():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["run", "--out", "o"])
    assert exc_info.value.code == 2


def test_docs_and_docs_dir_are_mutually_exclusive():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["run", "--video", "a.mp4", "--out", "o", "--docs", "a.md", "--docs-dir", "somedir"]
        )


def test_parse_stages_helper():
    assert _parse_stages(None) is None
    assert _parse_stages("") is None
    assert _parse_stages("context,align") == [Stage.CONTEXT, Stage.ALIGN]
    with pytest.raises(ValueError):
        _parse_stages("bogus")


def test_config_from_args_maps_flags_onto_config_sections():
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--video",
            "a.mp4",
            "--out",
            "o",
            "--no-ocr",
            "--no-embedding",
            "--ocr-backend",
            "rapid",
            "--whisper-model",
            "small.en",
        ]
    )
    config = config_from_args(args)
    assert config.ocr.enabled is False
    assert config.context.embeddings_enabled is False
    assert config.ocr.backend == "rapid"
    assert config.transcription.model_size == "small.en"


def test_config_from_args_with_no_overrides_returns_defaults():
    parser = build_parser()
    args = parser.parse_args(["run", "--video", "a.mp4", "--out", "o"])
    assert config_from_args(args) == PipelineConfig()


def test_config_from_args_file_then_explicit_flag_precedence(tmp_path):
    config_path = tmp_path / "cfg.json"
    PipelineConfig().replace(transcription={"model_size": "small.en", "device": "cuda"}).to_json(config_path)

    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--video",
            "a.mp4",
            "--out",
            "o",
            "--config",
            str(config_path),
            "--whisper-model",
            "medium.en",
        ]
    )
    config = config_from_args(args)
    # Explicit --whisper-model flag wins over the file's model_size.
    assert config.transcription.model_size == "medium.en"
    # But the file's other field, not overridden by any flag, is preserved.
    assert config.transcription.device == "cuda"


def test_print_config_outputs_valid_json_and_returns_zero(capsys):
    exit_code = main(["--print-config"])
    assert exit_code == 0
    data = json.loads(capsys.readouterr().out)
    assert "transcription" in data
    assert "frames" in data


def test_no_command_and_no_print_config_is_an_error():
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_invalid_stages_value_causes_system_exit_2(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        main(["run", "--video", "a.mp4", "--out", str(tmp_path), "--stages", "bogus"])
    assert exc_info.value.code == 2


def test_frames_subcommand_parses_required_args():
    parser = build_parser()
    args = parser.parse_args(["frames", "--video", "a.mp4", "--vtt", "t.vtt", "--out", "o"])
    assert args.command == "frames"
    assert args.transcript_path == "t.vtt"


def test_align_requires_docs_or_docs_dir():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["align", "--context", "c.json", "--out", "o"])
