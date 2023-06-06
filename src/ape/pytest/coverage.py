from pathlib import Path
from typing import Iterable, Optional

from ethpm_types.source import ContractSource, SourceLocation

from ape.logging import logger
from ape.pytest.config import ConfigWrapper
from ape.types import CoverageReport, SourceTraceback
from ape.types.coverage import CoverageProject
from ape.utils import (
    ManagerAccessMixin,
    get_current_timestamp,
    get_relative_path,
    parse_coverage_table,
)


class CoverageData(ManagerAccessMixin):
    def __init__(self, base_path: Path, sources: Iterable[ContractSource]):
        self.base_path = base_path
        self.sources = list(sources)
        self._report: Optional[CoverageReport] = None
        self._init_coverage_profile()  # Should set self._report to not None.

    @property
    def report(self) -> CoverageReport:
        if self._report is None:
            return self._init_coverage_profile()

        return self._report

    def reset(self):
        self._report = None
        self._init_coverage_profile()

    def _init_coverage_profile(
        self,
    ) -> CoverageReport:
        # source_id -> pc(s) -> times hit
        # TODO: Potentially may want another Compiler API for this.
        project_coverage = CoverageProject(name=self.config_manager.name or "__local__")

        for src in self.sources:
            source_coverage = project_coverage.include(src.source_id)
            contract_coverage = source_coverage.include(
                src.contract_type.name or "__UnknownContract__"
            )

            for pc, item in src.pcmap.__root__.items():
                pc_int = int(pc)
                if pc_int < 0:
                    continue

                location: Optional[SourceLocation]
                if item.get("location"):
                    location_list = item["location"]
                    if not isinstance(location_list, (list, tuple)):
                        raise TypeError(f"Unexpected location type '{type(location_list)}'.")

                    # NOTE: Only doing 0 because mypy for some reason thinks it is optional.
                    location = (
                        location_list[0] or 0,
                        location_list[1] or 0,
                        location_list[2] or 0,
                        location_list[3] or 0,
                    )
                else:
                    location = None

                if location is not None and not isinstance(location, tuple):
                    # Only really for mypy.
                    raise TypeError(f"Received unexpected type for location '{location}'.")

                if not location and not item.get("dev"):
                    # Not a statement we can measure.
                    continue

                def _include_from(_name: str, _full_name: str):
                    function_coverage = contract_coverage.include(_name, _full_name)
                    tag = str(item["dev"]) if item.get("dev") else None
                    function_coverage.profile_statement(pc_int, location=location, tag=tag)

                if location:
                    function = src.lookup_function(location)
                    if not function:
                        # Not sure if this happens.
                        continue

                    matching_abis = [
                        a for a in src.contract_type.methods if a.name == function.name
                    ]
                    if len(matching_abis) > 1:
                        # Is likely part of auto-generated methods.
                        # Put one one of the ABIs that is not the longest.
                        # If there is an ABI that is still has the same amount of statements
                        # as the longest, use that ABI for this extra statement.
                        # TODO: Find a more accurate way to do this, maybe using ape-vyper.

                        # Check if this touches stuff outside the function content.
                        # If it does, that may mean something if there are mutliple ABIs defined.
                        is_outside_content = (
                            location[0] < function.content.begin_lineno
                            or location[2] > function.content.end_lineno
                        )
                        longest_abi = max(matching_abis, key=lambda x: len(x.inputs))
                        other_abis = [x for x in matching_abis if x != longest_abi]
                        longest_abi_function = contract_coverage.get_function(longest_abi.selector)
                        if is_outside_content and longest_abi_function:
                            # Use the function with the same or less valid lines as the root.
                            # This way, we are at least sure to cover every auto-generated method
                            # at least once.
                            smallest_func = longest_abi_function
                            for other_abi in other_abis:
                                func = contract_coverage.get_function(other_abi.selector)
                                if func and func.lines_valid <= smallest_func.lines_valid:
                                    smallest_func = func

                                elif not func:
                                    # Use this function.
                                    _include_from(other_abi.name, other_abi.selector)
                                    smallest_func = None

                            if smallest_func:
                                _include_from(smallest_func.name, smallest_func.full_name)

                        elif is_outside_content and other_abis:
                            # Use first other ABI
                            _include_from(other_abis[0].name, other_abis[0].selector)

                        else:
                            # Not sure this happens.
                            _include_from(longest_abi.name, longest_abi.selector)

                    elif len(matching_abis) == 1:
                        _include_from(function.name, matching_abis[0].selector)

                    elif len(matching_abis) == 0:
                        # Is likely an internal method.
                        _include_from(function.name, function.full_name)

                else:
                    _include_from("__builtin__", "__builtin__")

        timestamp = int(round(get_current_timestamp()))
        report = CoverageReport(projects=[project_coverage], timestamp=timestamp)
        self._report = report
        return report

    def cover(self, src_path: Path, pcs: Iterable[int]):
        source_id = str(get_relative_path(src_path.absolute(), self.base_path))

        if source_id not in self.report.sources:
            # The source is not tracked for coverage.
            return

        handled_pcs = set()
        for pc in pcs:
            if pc < 0:
                continue

            source_coverage = self.report.get_source_coverage(source_id)
            if not source_coverage:
                continue

            for statement in source_coverage.statements:
                if pc in statement.pcs:
                    statement.hit_count += 1
                    handled_pcs.add(pc)

        unhandled_pcs = set(pcs) - handled_pcs
        if unhandled_pcs:
            # Maybe a bug in ape.
            logger.debug(f"Unhandled PCs: '{','.join([f'{x}' for x in unhandled_pcs])}'")


class CoverageTracker(ManagerAccessMixin):
    def __init__(self, config_wrapper: ConfigWrapper):
        self.config_wrapper = config_wrapper
        sources = self.project_manager._contract_sources
        self.data = CoverageData(self.project_manager.contracts_folder, sources)

    @property
    def enabled(self) -> bool:
        return self.config_wrapper.track_coverage

    def cover(self, traceback: SourceTraceback):
        """
        Track the coverage from the given source traceback.

        Args:
            traceback (:class:`~ape.types.trace.SourceTraceback`):
              The class instance containing all the information regarding
              sources covered for a particular transaction.
        """
        for control_flow in traceback:
            if not control_flow.source_path or not control_flow.pcs:
                continue

            self.data.cover(control_flow.source_path, control_flow.pcs)

    def show_session_coverage(self) -> bool:
        if not self.data or not self.data.report or not self.data.report.sources:
            return False

        table = parse_coverage_table(self.data.report)
        self.chain_manager._reports.echo(table)
        return True
