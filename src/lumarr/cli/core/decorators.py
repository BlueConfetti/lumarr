"""Dependency injection decorators for CLI commands."""

from functools import wraps
import sys

import rich_click as click

from ..commands.common import (
    console,
    print_connection_test,
    print_connection_success,
    print_connection_failure,
)
from .exceptions import ConnectionError


def with_config(f):
    """
    Inject config from context.

    Usage:
        @with_config
        def command(config, ...):
            pass
    """
    @wraps(f)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        config = ctx.obj.config
        return f(config=config, **kwargs)
    return wrapper


def with_database(f):
    """
    Inject initialized database with automatic resource management.

    Usage:
        @with_database
        def command(database, ...):
            pass
    """
    @wraps(f)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        from ..services.database import DatabaseService

        with DatabaseService(ctx.obj.db_path) as database:
            return f(database=database, **kwargs)
    return wrapper


def with_plex(f):
    """
    Inject initialized and tested Plex API.

    Usage:
        @with_plex
        def command(plex, ...):
            pass
    """
    @wraps(f)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        from ..services.plex import PlexService
        from ..services.database import DatabaseService

        print_connection_test("Plex")

        # Create database and Plex service in nested context managers
        with DatabaseService(ctx.obj.db_path) as database:
            plex_service = PlexService.from_config(ctx.obj.config, database)

            with plex_service as plex:
                if not plex.ping():
                    print_connection_failure("Plex", "Check your token in config.yaml")
                    sys.exit(1)

                print_connection_success("Plex")
                return f(ctx, plex=plex, **kwargs)
    return wrapper


def with_sonarr(optional=False):
    """
    Inject initialized and tested Sonarr API.

    Args:
        optional: If True, pass None if Sonarr is disabled. If False, exit on error.

    Usage:
        @with_sonarr(optional=True)
        def command(sonarr, ...):
            pass
    """
    def decorator(f):
        @wraps(f)
        @click.pass_context
        def wrapper(ctx, *args, **kwargs):
            from ..services.sonarr import SonarrService

            if not ctx.obj.config.get("sonarr.enabled", False):
                if optional:
                    return f(ctx, sonarr=None, **kwargs)
                print_connection_failure("Sonarr", "Enable Sonarr in config.yaml")
                sys.exit(1)

            print_connection_test("Sonarr")
            sonarr_service = SonarrService.from_config(ctx.obj.config)

            with sonarr_service as sonarr:
                if not sonarr.test_connection():
                    print_connection_failure("Sonarr", "Check your URL and API key in config.yaml")
                    if not optional:
                        sys.exit(1)
                    return f(ctx, sonarr=None, **kwargs)

                print_connection_success("Sonarr")
                return f(ctx, sonarr=sonarr, **kwargs)
        return wrapper
    return decorator


def with_radarr(optional=False):
    """
    Inject initialized and tested Radarr API.

    Args:
        optional: If True, pass None if Radarr is disabled. If False, exit on error.

    Usage:
        @with_radarr(optional=True)
        def command(radarr, ...):
            pass
    """
    def decorator(f):
        @wraps(f)
        @click.pass_context
        def wrapper(ctx, *args, **kwargs):
            from ..services.radarr import RadarrService

            if not ctx.obj.config.get("radarr.enabled", False):
                if optional:
                    return f(ctx, radarr=None, **kwargs)
                print_connection_failure("Radarr", "Enable Radarr in config.yaml")
                sys.exit(1)

            print_connection_test("Radarr")
            radarr_service = RadarrService.from_config(ctx.obj.config)

            with radarr_service as radarr:
                if not radarr.test_connection():
                    print_connection_failure("Radarr", "Check your URL and API key in config.yaml")
                    if not optional:
                        sys.exit(1)
                    return f(ctx, radarr=None, **kwargs)

                print_connection_success("Radarr")
                return f(ctx, radarr=radarr, **kwargs)
        return wrapper
    return decorator


def with_tmdb(optional=True):
    """
    Inject initialized TMDB API.

    Args:
        optional: If True, pass None if TMDB is not configured (default True)

    Usage:
        @with_tmdb(optional=True)
        def command(tmdb, ...):
            pass
    """
    def decorator(f):
        @wraps(f)
        @click.pass_context
        def wrapper(ctx, *args, **kwargs):
            from ...api.tmdb import TmdbApi

            tmdb_key = ctx.obj.config.get("tmdb.api_key")
            if not tmdb_key:
                if optional:
                    return f(ctx, tmdb=None, **kwargs)
                print_connection_failure("TMDB", "Add tmdb.api_key to config.yaml")
                sys.exit(1)

            tmdb = TmdbApi(api_key=tmdb_key)
            if tmdb.is_configured():
                print_connection_success("TMDB")

            return f(ctx, tmdb=tmdb, **kwargs)
        return wrapper
    return decorator


def with_letterboxd(f):
    """
    Inject Letterboxd resolver.

    Usage:
        @with_letterboxd
        def command(letterboxd_resolver, ...):
            pass
    """
    @wraps(f)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        from ..services.letterboxd import LetterboxdResolver

        resolver = LetterboxdResolver(ctx.obj.config)
        return f(ctx, letterboxd_resolver=resolver, **kwargs)
    return wrapper
