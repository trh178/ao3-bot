import pytest

from ao3bot.cli import main
from ao3bot.state import SCHEMA_VERSION

from .conftest import MINIMAL


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for command in ("poll", "build", "push", "serve", "status", "doctor"):
        assert command in out


def test_doctor_ok_and_creates_state_db(write_config, capsys):
    path = write_config(MINIMAL)
    assert main(["--config", str(path), "doctor"]) == 0
    assert (path.parent / "data" / "state.db").is_file()
    out = capsys.readouterr().out
    assert out.rstrip().endswith("OK")
    assert f"schema v{SCHEMA_VERSION}" in out


def test_doctor_twice_is_fine(write_config):
    path = write_config(MINIMAL)
    assert main(["--config", str(path), "doctor"]) == 0
    assert main(["--config", str(path), "doctor"]) == 0


def test_broken_config_is_one_line(write_config, capsys):
    path = write_config("[device]\n")
    assert main(["--config", str(path), "doctor"]) == 1
    err = capsys.readouterr().err.strip()
    assert "\n" not in err
    assert "host is required" in err


def test_missing_config_file(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "nope.toml"), "doctor"]) == 1
    assert "not found" in capsys.readouterr().err


def test_password_never_printed(write_config, capsys):
    path = write_config('[ao3]\nusername = "someone"\npassword = "hunter2-secret"\n' + MINIMAL)
    assert main(["--config", str(path), "doctor"]) == 0
    captured = capsys.readouterr()
    assert "hunter2-secret" not in captured.out + captured.err
    assert "someone" in captured.out


@pytest.mark.parametrize(
    "argv, phase",
    [(["poll"], 3), (["build", "123"], 4), (["serve"], 9), (["status"], 9)],
)
def test_unbuilt_commands_name_their_phase(argv, phase, capsys):
    assert main(argv) == 2
    assert f"phase {phase}" in capsys.readouterr().err
