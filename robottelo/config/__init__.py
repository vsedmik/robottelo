import builtins
import logging
import os
from pathlib import Path
from urllib.parse import urlunsplit

from dynaconf import LazySettings
from dynaconf.validator import ValidationError
from nailgun.config import ServerConfig

from robottelo.config.validators import VALIDATORS
from robottelo.logging import logger, robottelo_root_dir

if not os.getenv('ROBOTTELO_DIR'):
    # dynaconf robottelo file uses ROBOTELLO_DIR for screenshots
    os.environ['ROBOTTELO_DIR'] = str(robottelo_root_dir)


def get_settings():
    """Return Lazy settings object after validating

    :return: A validated Lazy settings object
    """
    if getattr(builtins, "__sphinx_build__", False):
        return None
    settings = LazySettings(
        envvar_prefix="ROBOTTELO",
        core_loaders=["YAML"],
        root_path=str(robottelo_root_dir),
        settings_file="settings.yaml",
        preload=["conf/*.yaml"],
        includes=["settings.local.yaml", ".secrets.yaml", ".secrets_*.yaml"],
        envless_mode=True,
        lowercase_read=True,
        load_dotenv=True,
    )
    settings.validators.register(**VALIDATORS)
    try:
        settings.validators.validate()
    except ValidationError as err:
        if settings.robottelo.settings.get('ignore_validation_errors'):
            logger.warning(f'Dynaconf validation failed with\n{err}')
        else:
            raise err
    return settings


settings = get_settings()
robottelo_tmp_dir = Path(settings.robottelo.tmp_dir)
robottelo_tmp_dir.mkdir(parents=True, exist_ok=True)


def get_credentials():
    """Return credentials for interacting with a Foreman deployment API.

    :return: A username-password pair.
    :rtype: tuple

    """
    username = settings.server.admin_username
    password = settings.server.admin_password
    return (username, password)


def get_url():
    """Return the base URL of the Foreman deployment being tested.

    The following values from the config file are used to build the URL:

    * ``[server] scheme`` (default: https)
    * ``[server] hostname`` (required)
    * ``[server] port`` (default: none)

    Setting ``port`` to 80 does *not* imply that ``scheme`` is 'https'. If
    ``port`` is 80 and ``scheme`` is unset, ``scheme`` will still default
    to 'https'.

    :return: A URL.
    :rtype: str

    """
    hostname = settings.server.get('hostname')
    scheme = settings.server.scheme
    port = settings.server.port
    if port is not None:
        hostname = f"{hostname}:{port}"

    return urlunsplit((scheme, hostname, '', '', ''))


def admin_nailgun_config():
    """Return a NailGun configuration file constructed from default admin user credentials.

    :return: ``nailgun.config.ServerConfig`` object, populated from admin user credentials.

    """
    return ServerConfig(get_url(), get_credentials(), verify=settings.server.verify_ca)


def user_nailgun_config(username=None, password=None):
    """Return a NailGun configuration file constructed from default values.

    :param user: The ```nailgun.entities.User``` object of an user with additional passwd
        property/attribute

    :return: ``nailgun.config.ServerConfig`` object, populated from user parameter object else
        with values from ``robottelo.config.settings``

    """
    creds = (username, password)
    return ServerConfig(get_url(), creds, verify=settings.server.verify_ca)


def setting_is_set(option):
    """Return either ``True`` or ``False`` if a Robottelo section setting is
    set or not respectively.
    """
    # Example: `settings.clients`
    # TODO: Use dynaconf 3.2 selective validation
    # Within the split world of Legacy settings and dynaconf, there is a limitation on validating
    # against the dynaconf settings within the scope of this method, and its use to skip tests.
    # With dynaconf 3.2, selective validation is available, and this is a perfect use for it.
    # Otherwise dynaconf validation is done above when the instance is created
    # Validation misses are allowed while the SettingsFacade still exists, because the opposite
    # configuration provider may have that field and will resolve.
    from dynaconf.utils.boxing import DynaBox

    opt_inst = getattr(settings, option, None)
    if opt_inst is None:
        raise ValueError(f'Setting {option} did not resolve in settings')
    if hasattr(opt_inst, 'validate'):
        return opt_inst.validate()
    return isinstance(opt_inst, DynaBox)


def configure_nailgun():
    """Configure NailGun's entity classes.

    Do the following:

    * Set ``entity_mixins.CREATE_MISSING`` to ``True``. This causes method
        ``EntityCreateMixin.create_raw`` to generate values for empty and
        required fields.
    * Set ``nailgun.entity_mixins.DEFAULT_SERVER_CONFIG`` to whatever is
        returned by :meth:`robottelo.helpers.get_nailgun_config`. See
        ``robottelo.entity_mixins.Entity`` for more information on the effects
        of this.
    * Set a default value for ``nailgun.entities.GPGKey.content``.
    """
    from nailgun import entities, entity_mixins
    from nailgun.config import ServerConfig

    entity_mixins.CREATE_MISSING = True
    entity_mixins.DEFAULT_SERVER_CONFIG = ServerConfig(
        get_url(), get_credentials(), verify=settings.server.verify_ca
    )
    gpgkey_init = entities.GPGKey.__init__

    def patched_gpgkey_init(self, server_config=None, **kwargs):
        """Set a default value on the ``content`` field."""
        gpgkey_init(self, server_config, **kwargs)
        self._fields['content'].default = str(
            Path().joinpath('tests/foreman/data/valid_gpg_key.txt')
        )

    entities.GPGKey.__init__ = patched_gpgkey_init


configure_nailgun()


def configure_airgun():
    """Pass required settings to AirGun"""
    import airgun

    airgun.settings.configure(
        {
            'airgun': {
                'verbosity': logging.getLevelName(logger.getEffectiveLevel()),
                'tmp_dir': settings.robottelo.tmp_dir,
            },
            'satellite': {
                'hostname': settings.server.get('hostname', None),
                'password': settings.server.admin_password,
                'username': settings.server.admin_username,
            },
            'selenium': {
                'browser': settings.ui.browser,
                'screenshots_path': settings.ui.screenshots_path,
                'webdriver': settings.ui.webdriver,
                'webdriver_binary': settings.ui.webdriver_binary,
            },
            'webkaifuku': {'config': settings.ui.webkaifuku},
        }
    )


configure_airgun()
