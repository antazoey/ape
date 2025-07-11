import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from ape.cli.arguments import contract_file_paths_argument
from ape.cli.options import (
    ape_cli_context,
    config_override_option,
    excluded_compilers_option,
    project_option,
)

if TYPE_CHECKING:
    from ethpm_types import ContractType


def _include_dependencies_callback(ctx, param, value):
    return value or ctx.obj.config_manager.get_config("compile").include_dependencies


@click.command(short_help="Compile select contract source files")
@ape_cli_context()
@project_option()
@contract_file_paths_argument()
@click.option(
    "-f",
    "--force",
    "use_cache",
    flag_value=False,
    default=True,
    is_flag=True,
    help="Force recompiling selected contracts",
)
@click.option(
    "-s",
    "--size",
    "display_size",
    default=False,
    is_flag=True,
    help="Show deployment bytecode size for all contracts",
)
@click.option(
    "--include-dependencies",
    is_flag=True,
    help="Also compile dependencies",
    callback=_include_dependencies_callback,
)
@excluded_compilers_option()
@config_override_option()
def cli(
    cli_ctx,
    project,
    file_paths: set[Path],
    use_cache: bool,
    display_size: bool,
    include_dependencies,
    excluded_compilers: list[str],
    config_override,
):
    """
    Compiles the manifest for this project and saves the results
    back to the manifest.

    Note that ape automatically recompiles any changed contracts each time
    a project is loaded. You do not have to manually trigger a recompile.
    """
    compiled = False
    errored = False

    if cfg := config_override:
        project.reconfigure(**cfg)

    if file_paths:
        contracts = {
            k: v.contract_type
            for k, v in project.load_contracts(
                *file_paths, use_cache=use_cache, excluded_compilers=excluded_compilers
            ).items()
        }
        cli_ctx.logger.success("'local project' compiled.")
        compiled = True
        if display_size:
            _display_byte_code_sizes(cli_ctx, contracts)

    if (include_dependencies or project.config.compile.include_dependencies) and len(
        project.dependencies
    ) > 0:
        for dependency in project.dependencies:
            if use_cache and dependency.compiled:
                continue

            # Even if compiling failed, we at least tried,
            # and so we don't need to warn "Nothing to compile".
            compiled = True
            try:
                contract_types: dict[str, ContractType] = {
                    c.contract_type.name: c.contract_type
                    for c in dependency.compile(use_cache=use_cache, allow_install=True).values()
                }
            except Exception as err:
                msg = f"Dependency '{dependency.name}' not installed. Reason: {err}"
                cli_ctx.logger.error(msg)
                errored = True
                continue

            cli_ctx.logger.success(f"'{dependency.project.name}' compiled.")
            if display_size:
                _display_byte_code_sizes(cli_ctx, contract_types)

    if not compiled:
        from ape.utils.os import clean_path  # perf: lazy import

        folder = clean_path(project.contracts_folder)
        cli_ctx.logger.warning(f"Nothing to compile ({folder}).")

    if errored:
        # Ensure exit code.
        sys.exit(1)


def _display_byte_code_sizes(cli_ctx, contract_types: dict[str, "ContractType"]):
    # Display bytecode size for *all* contract types (not just ones we compiled)
    code_size = []
    for contract in contract_types.values():
        if not contract.deployment_bytecode:
            continue  # Skip if not bytecode to display

        bytecode = contract.deployment_bytecode.bytecode

        if bytecode:
            code_size.append((contract.name, len(bytecode) // 2))

    if not code_size:
        cli_ctx.logger.info("No contracts with bytecode to display")
        return

    click.echo()
    click.echo("============ Deployment Bytecode Sizes ============")
    indent = max(len(i[0]) for i in code_size)  # type: ignore
    for name, size in sorted(code_size, key=lambda k: k[1], reverse=True):
        pct = size / 24577
        # pct_color = color(next((i[1] for i in CODESIZE_COLORS if pct >= i[0]), ""))
        # TODO Get colors fixed for bytecode size output
        # click.echo(f"  {name:<{indent}}  -  {size:>6,}B  ({pct_color}{pct:.2%}{color})")
        click.echo(f"  {name:<{indent}}  -  {size:>6,}B  ({pct:.2%})")

    click.echo()
