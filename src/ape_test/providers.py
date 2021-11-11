from typing import Iterator

from eth_tester.backends import PyEVMBackend  # type: ignore
from eth_tester.exceptions import TransactionFailed  # type: ignore
from eth_utils.exceptions import ValidationError
from web3 import EthereumTesterProvider, Web3

from ape.api import ReceiptAPI, TestProviderAPI, TransactionAPI
from ape.exceptions import ContractLogicError, OutOfGasError, VirtualMachineError


class LocalNetwork(TestProviderAPI, Web3Provider):
    _web3: Web3 = None  # type: ignore

    def connect(self):
        pass

    def disconnect(self):
        pass

    def update_settings(self, new_settings: dict):
        pass

    def __post_init__(self):
        self._tester = PyEVMBackend.from_mnemonic(self.config["mnemonic"])
        self._web3 = Web3(EthereumTesterProvider(ethereum_tester=self._tester))

    def estimate_gas_cost(self, txn: TransactionAPI) -> int:
        try:
            return self._web3.eth.estimate_gas(txn.as_dict())  # type: ignore
        except TransactionFailed as err:
            err_message = str(err).split("execution reverted: ")[-1]
            raise ContractLogicError(err_message) from err

    @property
    def chain_id(self) -> int:
        return self._web3.eth.chain_id

    @property
    def gas_price(self) -> int:
        # NOTE: Test chain doesn't care about gas prices
        return 0

    @property
    def priority_fee(self) -> int:
        """
        Returns the current max priority fee per gas in wei.
        """
        return self._web3.eth.max_priority_fee

    @property
    def base_fee(self) -> int:
        block = self._web3.eth.get_block("latest")
        return block.baseFeePerGas

    def get_nonce(self, address: str) -> int:
        return self._web3.eth.get_transaction_count(address)  # type: ignore

    def get_balance(self, address: str) -> int:
        return self._web3.eth.get_balance(address)  # type: ignore

    def get_code(self, address: str) -> bytes:
        return self._web3.eth.get_code(address)  # type: ignore

    def send_call(self, txn: TransactionAPI) -> bytes:
        data = txn.as_dict()
        if "gas" not in data or data["gas"] == 0:
            data["gas"] = int(1e12)

        return self._web3.eth.call(data)

    def get_transaction(self, txn_hash: str) -> ReceiptAPI:
        # TODO: Work on API that let's you work with ReceiptAPI and re-send transactions
        receipt = self._web3.eth.wait_for_transaction_receipt(txn_hash)  # type: ignore
        txn = self._web3.eth.get_transaction(txn_hash)  # type: ignore
        return self.network.ecosystem.receipt_class.decode({**txn, **receipt})

    def send_transaction(self, txn: TransactionAPI) -> ReceiptAPI:
        try:
            txn_hash = self._web3.eth.send_raw_transaction(txn.encode())
        except ValidationError as err:
            raise VirtualMachineError(err) from err
        except TransactionFailed as err:
            err_message = str(err).split("execution reverted: ")[-1]
            raise ContractLogicError(err_message) from err

        receipt = self.get_transaction(txn_hash.hex())
        if txn.gas_limit is not None and receipt.ran_out_of_gas(txn.gas_limit):
            raise OutOfGasError()

        return receipt

    def get_events(self, **filter_params) -> Iterator[dict]:
        return iter(self._web3.eth.get_logs(filter_params))  # type: ignore

    def snapshot(self) -> str:
        return self._tester.take_snapshot()

    def revert(self, snapshot_id: str):
        if snapshot_id:
            return self._tester.revert_to_snapshot(snapshot_id)
