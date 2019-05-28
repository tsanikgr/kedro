# Copyright 2018-2019 QuantumBlack Visual Analytics Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
# NONINFRINGEMENT. IN NO EVENT WILL THE LICENSOR OR OTHER CONTRIBUTORS
# BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF, OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# The QuantumBlack Visual Analytics Limited (“QuantumBlack”) name and logo
# (either separately or in combination, “QuantumBlack Trademarks”) are
# trademarks of QuantumBlack. The License does not grant you any right or
# license to the QuantumBlack Trademarks. You may not use the QuantumBlack
# Trademarks or any confusingly similar mark as a trademark for your product,
#     or use the QuantumBlack Trademarks in any other manner that might cause
# confusion in the marketplace, including but not limited to in advertising,
# on websites, or on software.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""kedro is a CLI for creating Kedro projects.

This module implements commands available from the kedro CLI.
"""
import glob
import importlib
import os
import re
import shutil
import sys
import traceback
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, List, Union

import click
import pkg_resources
import yaml
from cookiecutter.main import cookiecutter

import kedro.config.default_logger  # noqa
from kedro import __version__ as version
from kedro.cli.utils import CommandCollection, KedroCliError

KEDRO_PATH = os.path.dirname(kedro.__file__)
TEMPLATE_PATH = os.path.join(KEDRO_PATH, "template")
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

NO_DEFAULT = object()
_KEDRO_CONTEXT = {"verbose": True}

LOGO = r"""
 _            _
| | _____  __| |_ __ ___
| |/ / _ \/ _` | '__/ _ \
|   <  __/ (_| | | | (_) |
|_|\_\___|\__,_|_|  \___/
v{}
""".format(
    version
)


@click.group(context_settings=CONTEXT_SETTINGS, name="Kedro")
@click.version_option(version, "--version", "-V", help="Show version and exit")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="See extensive logging and error stack traces.",
)
def cli(verbose):
    """Kedro is a CLI for creating and using Kedro projects
    For more information, type ``kedro info``.

    When inside a Kedro project (created with `kedro new`) commands from
    the project's `kedro_cli.py` file will also be available here.
    """
    _KEDRO_CONTEXT["verbose"] = verbose


@cli.command()
def info():
    """Get more information about kedro.
    """
    click.secho(LOGO, fg="green")
    click.echo(
        "kedro allows teams to create analytics\n"
        "projects. It is developed as part of\n"
        "the Kedro initiative at QuantumBlack."
    )


@cli.command(short_help="Create a new kedro project.")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Non-interactive mode, using a configuration yaml file.",
)
def new(config):
    """Create a new kedro project, either interactively or from a
    configuration file.

    Create projects according to the Kedro default project template. This
    template is ideal for analytics projects and comes with a data
    architecture, folders for notebooks, configuration, source code, etc.

    \b
    ``kedro new``
    Create a new project interactively.

    \b
    You will have to provide four choices:
    * ``Output Directory`` - parent directory where new project directory
    should be created.
    * ``Project Name`` - name of the project, not to be confused with name of
    the project folder.
    * ``Repository Name`` - intended name of your project folder.
    * ``Package Name`` - intended name of your Python package.

    \b
    ``kedro new --config <config.yml>``
    ``kedro new -c <config.yml>``
    Create a new project from configuration.

    * ``config.yml`` - The configuration YAML must contain at the top level
                    the above parameters (output_dir, project_name, repo_name,
                    python_package).
    """
    _create_project(config, _KEDRO_CONTEXT["verbose"])


@cli.command(short_help="See the kedro API docs and introductory tutorial.")
def docs():
    """Display the API docs and introductory tutorial in the browser,
    using the packaged HTML doc files."""
    index_path = "file://" + os.path.realpath(
        os.path.join(
            os.path.realpath(__file__), os.pardir, os.pardir, "html", "index.html"
        )
    )
    click.echo("Opening " + index_path)
    webbrowser.open(index_path)


def _clean_pycache(project_path):
    # Since template is part of the Kedro package __pycache__ is generated.
    # This method recursively cleans all __pycache__ folders.
    to_delete = [
        os.path.join(project_path, filename)
        for filename in glob.iglob(project_path + "/**/*", recursive=True)
        if filename.endswith("__pycache__")
    ]

    for file in to_delete:  # pragma: no cover
        shutil.rmtree(file)


def _create_project(config_path: str, verbose: bool):
    """Implementation of the kedro new cli command.

    Args:
        config_path: In non-interactive mode, the path of the config.yml which
            should contain the project_name, output_dir and repo_name.
        verbose: Extensive debug terminal logs.
    """
    try:
        if config_path:
            config = _parse_config(config_path, verbose)
            config = _check_config_ok(config_path, config)
        else:
            config = _get_config_from_prompts()
        config.setdefault("kedro_version", version)

        result_path = cookiecutter(
            TEMPLATE_PATH,
            output_dir=config["output_dir"],
            no_input=True,
            extra_context=config,
        )
        if not config["include_example"]:
            paths_to_remove = [
                os.path.join(result_path, "data", "01_raw", "iris.csv"),
                os.path.join(
                    result_path, "src", config["python_package"], "nodes", "example.py"
                ),
            ]

            for path in paths_to_remove:
                os.remove(path)
        _clean_pycache(result_path)
        _print_kedro_new_success_message(result_path)
    except click.exceptions.Abort:  # pragma: no cover
        _handle_exception("User interrupt.")
    # we dont want the user to see a stack trace on the cli
    except Exception:  # pylint: disable=broad-except
        _handle_exception("Failed to generate project.")


def _get_config_from_prompts() -> Dict:
    """Ask user to provide necessary inputs.

    Returns:
        Resulting config dictionary.

    """

    def _get_user_input(
        text: str,
        default: Any = None,
        assert_or_check_funcs: Union[Callable, List[Callable]] = None,
    ) -> Any:
        """Get user input and validate it.

        Args:
            text: Text to display in command line prompt.
            default: Default value for the input.
            assert_or_check_funcs: List of functions to apply to user input.
                Value is overridden by function output if the latter is
                not None.

        Returns:
            Processed user value.

        """
        if callable(assert_or_check_funcs):
            assert_or_check_funcs = [assert_or_check_funcs]
        else:
            assert_or_check_funcs = assert_or_check_funcs or []
        while True:
            try:
                value = click.prompt(text, default=default)
                for _func in assert_or_check_funcs:
                    _func(value)
            except KedroCliError as exc:
                click.secho(str(exc), fg="red", err=True)
            else:
                break
        return value

    # set output directory to the current directory
    output_dir = os.path.abspath(os.path.curdir)

    # get project name
    project_name_prompt = _get_prompt_text(
        "Project Name:",
        "Please enter a human readable name for your new project.",
        "Spaces and punctuation are allowed.",
    )

    project_name = _get_user_input(project_name_prompt, default="New Kedro Project")

    normalized_project_name = re.sub(r"[^\w-]+", "-", project_name).lower().strip("-")

    # get repo name
    repo_name_prompt = _get_prompt_text(
        "Repository Name:",
        "Please enter a directory name for your new project repository.",
        "Alphanumeric characters, hyphens and underscores are allowed.",
        "Lowercase is recommended.",
    )
    repo_name = _get_user_input(
        repo_name_prompt, normalized_project_name, _assert_repo_name_ok
    )

    # get python package_name
    default_pkg_name = normalized_project_name.replace("-", "_")
    pkg_name_prompt = _get_prompt_text(
        "Python Package Name:",
        "Please enter a valid Python package name for your project package.",
        "Alphanumeric characters and underscores are allowed.",
        "Lowercase is recommended. Package name must start with a letter "
        "or underscore.",
    )
    python_package = _get_user_input(
        pkg_name_prompt, default_pkg_name, _assert_pkg_name_ok
    )

    # option for whether iris example code is included in the project
    code_example_prompt = _get_prompt_text(
        "Generate Example Pipeline:",
        "Do you want to generate an example pipeline in your project?",
        "Good for first-time users. (default=N)",
    )
    include_example = click.confirm(code_example_prompt, default=False)

    return {
        "output_dir": output_dir,
        "project_name": project_name,
        "repo_name": repo_name,
        "python_package": python_package,
        "include_example": include_example,
    }


def _parse_config(config_path: str, verbose: bool) -> Dict:
    """Parse the config YAML from its path.

    Args:
        config_path: The path of the config.yml file.
        verbose: Print the config contents.

    Raises:
        Exception: If the file cannot be parsed.

    Returns:
        The config as a dictionary.

    """
    try:
        with open(config_path, "r") as config_file:
            config = yaml.safe_load(config_file)

        if verbose:
            click.echo(config_path + ":")
            click.echo(yaml.dump(config, default_flow_style=False))

        return config

    except Exception as exc:
        click.secho("Failed to parse " + config_path, fg="red", err=True)
        _show_example_config()
        raise exc


def _check_config_ok(config_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check that the configuration file contains all needed variables.

    Args:
        config_path: The path of the config file.
        config: The config as a dictionary.

    Returns:
        Config dictionary.

    Raises:
        KedroCliError: If the config file is empty or does not contain all
            keys from template/cookiecutter.json and output_dir.

    """
    if config is None:
        _show_example_config()
        raise KedroCliError(config_path + " is empty")

    required_in_config = _get_default_config().keys()

    for var in required_in_config:
        if var not in config:
            click.echo("\n" + config_path + ":")
            click.echo(yaml.dump(config, default_flow_style=False))
            _show_example_config()

            raise KedroCliError("[" + var + "] not found in " + config_path)

    config["output_dir"] = _fix_user_path(config["output_dir"])
    _assert_output_dir_ok(config["output_dir"])
    _assert_repo_name_ok(config["repo_name"])
    _assert_pkg_name_ok(config["python_package"])
    _assert_include_example_ok(config["include_example"])
    return config


def _get_default_config():
    default_config_path = os.path.join(TEMPLATE_PATH, "default_config.yml")
    with open(default_config_path) as default_config_file:
        default_config = yaml.safe_load(default_config_file)
    return default_config


def _assert_output_dir_ok(output_dir: str):
    """Check that output directory exists.

    Args:
        output_dir: Output directory path.

    Raises:
        KedroCliError: If the output directory does not exist.

    """
    if not os.path.exists(output_dir):
        message = (
            "`{}` is not a valid output directory. "
            "It must be a relative or absolute path "
            "to an existing directory.".format(output_dir)
        )
        raise KedroCliError(message)


def _assert_pkg_name_ok(pkg_name: str):
    """Check that python package name is in line with PEP8 requirements.

    Args:
        pkg_name: Candidate Python package name.

    Raises:
        KedroCliError: If package name violates the requirements.
    """

    base_message = "`{}` is not a valid Python package name.".format(pkg_name)
    if not re.match(r"^[a-zA-Z_]", pkg_name):
        message = base_message + " It must start with a letter or underscore."
        raise KedroCliError(message)
    if len(pkg_name) < 2:
        message = base_message + " It must be at least 2 characters long."
        raise KedroCliError(message)
    if not re.match(r"^\w+$", pkg_name[1:]):
        message = (
            base_message + " It must contain only letters, "
            "digits, and/or underscores."
        )
        raise KedroCliError(message)


def _assert_repo_name_ok(repo_name):
    if not re.match(r"^\w+(-*\w+)*$", repo_name):
        message = (
            "`{}` is not a valid repository name. It must contain "
            "only word symbols and/or hyphens, must also start and "
            "end with alphanumeric symbol.".format(repo_name)
        )
        raise KedroCliError(message)


def _assert_include_example_ok(include_example):
    if not isinstance(include_example, bool):
        message = (
            "`{}` value for `include_example` is invalid. It must be a boolean value "
            "True or False.".format(include_example)
        )
        raise KedroCliError(message)


def _fix_user_path(output_dir):
    output_dir = output_dir or ""
    output_dir = os.path.expanduser(output_dir)

    result = os.path.abspath(output_dir)
    return result


def _show_example_config():
    click.secho("Example of valid config.yml:")
    default_config = _get_default_config()
    for key, value in default_config.items():
        click.secho(
            click.style(key + ": ", bold=True, fg="yellow")
            + click.style(str(value), fg="cyan")
        )
    click.echo("")


def _print_kedro_new_success_message(result):
    click.secho("Project generated in " + os.path.abspath(result), fg="green")
    click.secho(
        "Don't forget to initialise git and create a virtual environment. "
        "Refer to the Kedro documentation."
    )


def _get_prompt_text(title, *text):
    title = title.strip().title()
    title = click.style(title + "\n" + "=" * len(title), bold=True)
    prompt_text = [title] + list(text)
    return "\n".join(str(x).strip() for x in prompt_text) + "\n"


def get_project_context(key, default=NO_DEFAULT):  # pragma: no cover
    """Get a value from the project context."""
    try:
        kedro_cli = importlib.import_module("kedro_cli")
        kedro_context = _KEDRO_CONTEXT.copy()
        kedro_context.update(kedro_cli.__get_kedro_context__())
        value = kedro_context[key]
    except KeyError:
        if default is not NO_DEFAULT:
            return default
        _handle_exception(
            "`{}` not found in the context returned by "
            "__get_kedro_context__".format(key)
        )

    return value


def _get_plugin_command_groups(name):  # pragma: no cover
    entry_points = pkg_resources.iter_entry_points(
        group="kedro.{}_commands".format(name)
    )
    groups = []
    for entry_point in entry_points:
        try:
            groups.append(entry_point.load())
        except Exception:  # pylint: disable=broad-except
            _handle_exception(
                "Loading {} commands from {}".format(name, str(entry_point)), end=False
            )
    return groups


def main():  # pragma: no cover
    """Main entry point, look for a `kedro_cli.py` and if found add its
    commands to `kedro`'s then invoke the cli.
    """

    # run plugin initilization
    for entry_point in pkg_resources.iter_entry_points(group="kedro.init"):
        try:
            init_hook = entry_point.load()
            init_hook()
        except Exception:  # pylint: disable=broad-except
            _handle_exception("Initilizing {}".format(str(entry_point)), end=False)

    global_groups = [cli]
    global_groups.extend(_get_plugin_command_groups("global"))
    project_groups = []

    # load project commands from kedro_cli.py
    path = Path.cwd()
    kedro_cli_path = path / "kedro_cli.py"

    if kedro_cli_path.exists():
        try:
            sys.path.append(str(path))
            kedro_cli = importlib.import_module("kedro_cli")
            project_groups.extend(_get_plugin_command_groups("project"))
            project_groups.append(kedro_cli.cli)
        except Exception:  # pylint: disable=broad-except
            _handle_exception(
                "Cannot load commands from {}".format(str(kedro_cli_path))
            )
    CommandCollection(
        ("Global commands", global_groups),
        ("Project specific commands", project_groups),
    )()


def _handle_exception(msg, end=True):
    """Pretty print the current exception then exit."""
    if _KEDRO_CONTEXT["verbose"]:
        click.secho(traceback.format_exc(), nl=False, fg="yellow")
    else:
        etype, value, _ = sys.exc_info()
        click.secho(
            "".join(*traceback.format_exception_only(etype, value))
            + "Run with --verbose to see the full exception",
            fg="yellow",
        )
    if end:
        raise KedroCliError(msg)
    click.secho("Error: " + msg, fg="red")  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    main()
