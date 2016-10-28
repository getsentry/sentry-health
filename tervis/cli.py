import os
import sys
import click
import logging

from .environment import Environment


pass_environment = click.make_pass_decorator(Environment, ensure=True)


@click.group()
def cli():
    """Blah"""
    logging.basicConfig(level=logging.DEBUG)


@cli.command()
@pass_environment
def recorder(env):
    """Runs the recorder."""
    from .recorder import Recorder
    Recorder(env).run()


@cli.command()
@pass_environment
def generator(env):
    """Runs a dummy generator."""
    from .mockgenerator import MockGenerator
    MockGenerator(env).run()


@cli.command()
@pass_environment
def shell(env):
    """Runs a dummy generator."""
    import code
    banner = 'Python %s on %s\nEnvironment: %s' % (
        sys.version,
        sys.platform,
        env,
    )
    ctx = {}

    # Support the regular Python interpreter startup script if someone
    # is using it.
    startup = os.environ.get('PYTHONSTARTUP')
    if startup and os.path.isfile(startup):
        with open(startup, 'r') as f:
            eval(compile(f.read(), startup, 'exec'), ctx)

    ctx['env'] = env

    code.interact(banner=banner, local=ctx)


@cli.command()
@click.option('--host')
@click.option('--port', type=int)
@pass_environment
def apiserver(env, host, port):
    """Runs the api server."""
    from .apiserver import Server
    with env:
        with Server(env) as server:
            server.run(host=host, port=port)
