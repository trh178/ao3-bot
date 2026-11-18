import pytest

from ao3bot.config import ConfigError, load_config

from .conftest import MINIMAL, REPO

LOGGED_IN = '[ao3]\nusername = "someone"\npassword = "hunter2-secret"\n' + MINIMAL


def test_example_config_loads():
    cfg = load_config(REPO / "config.example.toml")
    assert cfg.ao3.sources == ("manual",)
    assert not cfg.ao3.logged_in
    assert cfg.device.folder == "/AO3"
    assert cfg.epub.max_image == (480, 800)


def test_defaults_fill_in(write_config):
    cfg = load_config(write_config(MINIMAL))
    assert cfg.ao3.poll_minutes == 30
    assert cfg.ao3.backfill_newest == 10
    assert cfg.device.name == "192.168.1.50"
    assert cfg.device.update_mode == "auto"
    assert cfg.data_dir == cfg.path.parent / "data"
    assert cfg.ao3.manual_ids_file == cfg.path.parent / "ids.txt"
    assert cfg.state_db == cfg.data_dir / "state.db"


def test_missing_host(write_config):
    with pytest.raises(ConfigError, match=r"\[device\] host is required"):
        load_config(write_config("[ao3]\npoll_minutes = 30\n"))


def test_bad_toml_names_the_line(write_config):
    with pytest.raises(ConfigError, match="not valid TOML.*line"):
        load_config(write_config('[device]\nhost = "x\n'))


def test_unknown_key_is_named(write_config):
    with pytest.raises(ConfigError, match="unknown key 'pasword'"):
        load_config(write_config('[ao3]\npasword = "x"\n' + MINIMAL))


def test_unknown_section_is_named(write_config):
    with pytest.raises(ConfigError, match=r"unknown section \[reader\]"):
        load_config(write_config(MINIMAL + '[reader]\nhost = "x"\n'))


def test_wrong_type(write_config):
    with pytest.raises(ConfigError, match="poll_minutes must be a whole number"):
        load_config(write_config('[ao3]\npoll_minutes = "30"\n' + MINIMAL))


def test_bool_is_not_a_number(write_config):
    with pytest.raises(ConfigError, match="poll_minutes must be a whole number"):
        load_config(write_config("[ao3]\npoll_minutes = true\n" + MINIMAL))


def test_poll_floor(write_config):
    with pytest.raises(ConfigError, match="at least 15"):
        load_config(write_config("[ao3]\npoll_minutes = 5\n" + MINIMAL))


def test_unknown_source(write_config):
    with pytest.raises(ConfigError, match="unknown source 'favorites'"):
        load_config(write_config('[ao3]\nsources = ["favorites"]\n' + MINIMAL))


def test_marked_for_later_needs_login(write_config):
    with pytest.raises(ConfigError, match="username and password"):
        load_config(write_config('[ao3]\nsources = ["marked_for_later"]\n' + MINIMAL))


def test_password_without_username(write_config):
    with pytest.raises(ConfigError, match="username is empty"):
        load_config(write_config('[ao3]\npassword = "x"\n' + MINIMAL))


def test_host_without_scheme(write_config):
    with pytest.raises(ConfigError, match="without http://"):
        load_config(write_config('[device]\nhost = "http://192.168.1.50"\n'))


@pytest.mark.parametrize("folder", ["AO3", "/AO3/", "/", "/.crosspoint"])
def test_bad_folder(write_config, folder):
    with pytest.raises(ConfigError, match="folder must look like"):
        load_config(write_config(MINIMAL + f'folder = "{folder}"\n'))


def test_bad_image_size(write_config):
    with pytest.raises(ConfigError, match="max_image"):
        load_config(write_config(MINIMAL + '[epub]\nmax_image = "big"\n'))


def test_logged_in_config(write_config):
    cfg = load_config(write_config(LOGGED_IN))
    assert cfg.ao3.logged_in
    assert cfg.secrets == ["hunter2-secret"]


def test_password_hidden_from_repr(write_config):
    cfg = load_config(write_config(LOGGED_IN))
    assert "hunter2-secret" not in repr(cfg)


def test_errors_never_echo_the_password(write_config):
    body = '[ao3]\nusername = "someone"\npassword = "hunter2-secret"\npoll_minutes = 1\n' + MINIMAL
    with pytest.raises(ConfigError) as e:
        load_config(write_config(body))
    assert "hunter2-secret" not in str(e.value)
