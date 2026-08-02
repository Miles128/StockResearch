"""CLI research subcommand wiring."""

from stockresearch.main import main


def test_research_help_exits_nonzero_without_subcommand() -> None:
    # argparse required subparser → SystemExit
    try:
        main(["research"])
        raised = False
    except SystemExit as exc:
        raised = True
        assert exc.code != 0
    assert raised


def test_hypothesis_list_presets() -> None:
    code = main(["research", "hypothesis", "--list-presets"])
    assert code == 0
