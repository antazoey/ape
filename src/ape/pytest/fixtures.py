from typing import Iterator, List

import pytest

from ape.api import TestAccountAPI
from ape.exceptions import BlockNotFoundError, ProviderNotConnectedError
from ape.logging import logger
from ape.managers.chain import ChainManager
from ape.managers.networks import NetworkManager
from ape.managers.project import ProjectManager
from ape.pytest.reports import reporter
from ape.utils import ManagerAccessMixin


class PytestApeFixtures(ManagerAccessMixin):
    # NOTE: Avoid including links, markdown, or rst in method-docs
    # for fixtures, as they are used in output from the command
    # `ape test -q --fixture` (`pytest -q --fixture`).

    def __init__(self):
        self._warned_for_unimplemented_snapshot = False

    @pytest.fixture(scope="session")
    def accounts(self) -> List[TestAccountAPI]:
        """
        A collection of pre-funded accounts.
        """

        return self.account_manager.test_accounts

    @pytest.fixture(scope="session")
    def chain(self) -> ChainManager:
        """
        Manipulate the blockchain, such as mine or change the pending timestamp.
        """

        return self.chain_manager

    @pytest.fixture(scope="session")
    def networks(self) -> NetworkManager:
        """
        Connect to other networks in your tests.
        """

        return self.network_manager

    @pytest.fixture(scope="session")
    def project(self) -> ProjectManager:
        """
        Access contract types and dependencies.
        """

        return self.project_manager

    def _isolation(self) -> Iterator[None]:
        """
        Isolation logic used to implement isolation fixtures for each pytest scope.
        """
        start_block = self.chain_manager.provider.get_block("latest").number
        snapshot_id = None
        try:
            snapshot_id = self.chain_manager.snapshot()
        except ProviderNotConnectedError:
            logger.warning("Provider became disconnected mid-test.")

        except NotImplementedError:
            if not self._warned_for_unimplemented_snapshot:
                logger.warning(
                    "The connected provider does not support snapshotting. "
                    "Tests will not be completely isolated."
                )
                self._warned_for_unimplemented_snapshot = True

        yield

        if snapshot_id is not None and snapshot_id in self.chain_manager._snapshots:
            try:
                # Track receipts
                try:
                    end_block = self.chain_manager.provider.get_block("latest").number
                    blocks = self.chain_manager.blocks.range(start_block, end_block + 1)
                except BlockNotFoundError:
                    # Snapshotting likely done in test
                    blocks = iter(())

                for block in blocks:
                    for transaction in block.transactions:
                        try:
                            receipt = self.provider.get_receipt(transaction.txn_hash.hex())
                        except BlockNotFoundError:
                            continue

                        # Ensure we cache call tree
                        if receipt.receiver:
                            reporter.add_gas_report(receipt)

                        self.chain_manager.restore(snapshot_id)

            except ProviderNotConnectedError:
                logger.warning("Provider became disconnected mid-test.")

    # isolation fixtures
    _session_isolation = pytest.fixture(_isolation, scope="session")
    _package_isolation = pytest.fixture(_isolation, scope="package")
    _module_isolation = pytest.fixture(_isolation, scope="module")
    _class_isolation = pytest.fixture(_isolation, scope="class")
    _function_isolation = pytest.fixture(_isolation, scope="function")
