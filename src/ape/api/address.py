from abc import abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Any, Optional

from ape.exceptions import AccountsError, ConversionError
from ape.types.address import AddressType
from ape.types.units import CurrencyValue
from ape.utils.basemodel import BaseInterface
from ape.utils.misc import log_instead_of_fail

if TYPE_CHECKING:
    from ape.api.transactions import ReceiptAPI, TransactionAPI
    from ape.managers.chain import AccountHistory
    from ape.types.vm import ContractCode


class BaseAddress(BaseInterface):
    """
    A base address API class. All account-types subclass this type.
    """

    @property
    def _base_dir_values(self) -> list[str]:
        """
        This exists because when you call ``dir(BaseAddress)``, you get the type's return
        value and not the instances. This allows base-classes to make use of shared
        ``IPython`` ``__dir__`` values.
        """

        # NOTE: mypy is confused by properties.
        #  https://github.com/python/typing/issues/1112

        return [
            str(BaseAddress.address.fget.__name__),  # type: ignore[attr-defined]
            str(BaseAddress.balance.fget.__name__),  # type: ignore[attr-defined]
            str(BaseAddress.code.fget.__name__),  # type: ignore[attr-defined]
            str(BaseAddress.codesize.fget.__name__),  # type: ignore[attr-defined]
            str(BaseAddress.nonce.fget.__name__),  # type: ignore[attr-defined]
            str(BaseAddress.is_contract.fget.__name__),  # type: ignore[attr-defined]
            "provider",  # Is a class property
        ]

    @property
    @abstractmethod
    def address(self) -> AddressType:
        """
        The address of this account. Subclasses must override and provide this value.
        """

    def __eq__(self, other: object) -> bool:
        """
        Compares :class:`~ape.api.BaseAddress` or ``str`` objects by converting to
        :class:`~ape.types.address.AddressType`.

        Returns:
            bool: comparison result
        """

        convert = self.conversion_manager.convert

        try:
            return convert(self, AddressType) == convert(other, AddressType)
        except ConversionError:
            # Check other __eq__
            return NotImplemented

    def __dir__(self) -> list[str]:
        """
        Display methods to IPython on ``a.[TAB]`` tab completion.
        Overridden to lessen amount of methods shown to only those that are useful.

        Returns:
            list[str]: Method names that IPython uses for tab completion.
        """
        return self._base_dir_values

    @log_instead_of_fail(default="<BaseAddress>")
    def __repr__(self) -> str:
        cls_name = getattr(type(self), "__name__", BaseAddress.__name__)
        return f"<{cls_name} {self.address}>"

    def __str__(self) -> str:
        """
        Convert this class to a ``str`` address.

        Returns:
            str: The stringified address.
        """
        return self.address

    def __hash__(self) -> int:
        """Return consistent hash for all address representations with the same value."""
        return hash(int(self.address, base=16))

    def __call__(self, **kwargs) -> "ReceiptAPI":
        """
        Call this address directly. For contracts, this may mean invoking their
        default handler.

        Args:
            **kwargs: Transaction arguments, such as ``sender`` or ``data``.

        Returns:
            :class:`~ape.api.transactions.ReceiptAPI`
        """

        txn = self.as_transaction(**kwargs)
        if "sender" in kwargs:
            if hasattr(kwargs["sender"], "call"):
                # AccountAPI
                sender = kwargs["sender"]
                return sender.call(txn, **kwargs)

            elif hasattr(kwargs["sender"], "prepare_transaction"):
                # BaseAddress (likely, a ContractInstance)
                prepare_transaction = kwargs["sender"].prepare_transaction(txn)
                return self.provider.send_transaction(prepare_transaction)

        elif "sender" not in kwargs and self.account_manager.default_sender is not None:
            return self.account_manager.default_sender.call(txn, **kwargs)

        return self.provider.send_transaction(txn)

    @property
    def nonce(self) -> int:
        """
        The number of transactions associated with the address.
        """

        return self.provider.get_nonce(self.address)

    @property
    def balance(self) -> int:
        """
        The total balance of the account.
        """
        bal = self.provider.get_balance(self.address)
        # By using CurrencyValue, we can compare with
        # strings like "1 ether".
        return CurrencyValue(bal)

    # @balance.setter
    # NOTE: commented out because of failure noted within `__setattr__`
    def _set_balance_(self, value: Any):
        if isinstance(value, str):
            value = self.conversion_manager.convert(value, int)

        self.provider.set_balance(self.address, value)

    def __setattr__(self, attr: str, value: Any) -> None:
        # NOTE: Need to do this until https://github.com/pydantic/pydantic/pull/2625 is figured out
        if attr == "balance":
            self._set_balance_(value)

        else:
            super().__setattr__(attr, value)

    @property
    def code(self) -> "ContractCode":
        """
        The raw bytes of the smart-contract code at the address.
        """
        # NOTE: Chain manager handles code caching.
        return self.chain_manager.get_code(self.address)

    @property
    def codesize(self) -> int:
        """
        The number of bytes in the smart contract.
        """
        code = self.code
        return len(code) if isinstance(code, bytes) else len(bytes.fromhex(code.lstrip("0x")))

    @property
    def is_contract(self) -> bool:
        """
        ``True`` when there is code associated with the address.
        """
        return self.codesize > 0

    @property
    def delegate(self) -> Optional["BaseAddress"]:
        """
        Check and see if Account has a "delegate" contract, which is a contract that this account
        delegates functionality to. This could be from many contexts, such as a Smart Wallet like
        Safe (https://github.com/ApeWorX/ape-safe) which has a Singleton class it forwards to, or
        an EOA using an EIP7702-style delegate. Returning ``None`` means that the account does not
        have a delegate.

        The default behavior is to use `:class:~ape.managers.ChainManager.get_delegate` to check if
        the account has a proxy, such as ``SafeProxy`` for ``ape-safe`` or an EIP7702 delegate.

        Returns:
            Optional[`:class:~ape.contracts.ContractInstance`]:
                The contract instance of the delegate contract (if available).
        """
        return self.chain_manager.get_delegate(self.address)

    @cached_property
    def history(self) -> "AccountHistory":
        """
        The list of transactions that this account has made on the current chain.
        """
        return self.chain_manager.history[self.address]

    def as_transaction(self, **kwargs) -> "TransactionAPI":
        sign = kwargs.pop("sign", False)
        converted_kwargs = self.conversion_manager.convert_method_kwargs(kwargs)
        tx = self.provider.network.ecosystem.create_transaction(
            receiver=self.address, **converted_kwargs
        )
        if sender := kwargs.get("sender"):
            if hasattr(sender, "prepare_transaction"):
                prepared = sender.prepare_transaction(tx)
                return (sender.sign_transaction(prepared) or prepared) if sign else prepared

        return tx

    def estimate_gas_cost(self, **kwargs) -> int:
        txn = self.as_transaction(**kwargs)
        return self.provider.estimate_gas_cost(txn)

    def prepare_transaction(self, txn: "TransactionAPI", **kwargs) -> "TransactionAPI":
        """
        Set default values on a transaction.

        Raises:
            :class:`~ape.exceptions.AccountsError`: When the account cannot afford the transaction
              or the nonce is invalid.
            :class:`~ape.exceptions.TransactionError`: When given negative required confirmations.

        Args:
            txn (:class:`~ape.api.transactions.TransactionAPI`): The transaction to prepare.
            **kwargs: Sub-classes, such as :class:`~ape.api.accounts.AccountAPI`, use additional kwargs.

        Returns:
            :class:`~ape.api.transactions.TransactionAPI`
        """

        # NOTE: Allow overriding nonce, assume user understands what this does
        if txn.nonce is None:
            txn.nonce = self.nonce
        elif txn.nonce < self.nonce:
            raise AccountsError("Invalid nonce, will not publish.")

        txn = self.provider.prepare_transaction(txn)

        if (
            txn.sender not in self.account_manager.test_accounts._impersonated_accounts
            and txn.total_transfer_value > self.balance
        ):
            raise AccountsError(
                f"Transfer value meets or exceeds account balance "
                f"for account '{self.address}' on chain '{self.provider.chain_id}' "
                f"using provider '{self.provider.name}'.\n"
                "Are you using the correct account / chain / provider combination?\n"
                f"(transfer_value={txn.total_transfer_value}, balance={self.balance})."
            )

        txn.sender = txn.sender or self.address
        return txn


class Address(BaseAddress):
    """
    A generic blockchain address.

    Typically, this is used when we do not know the contract type at a given address,
    or to refer to an EOA the user doesn't personally control.
    """

    def __init__(self, address: AddressType):
        self._address = address

    @property
    def address(self) -> AddressType:
        """
        The raw address type.

        Returns:
            :class:`~ape.types.address.AddressType`: An alias to
            `ChecksumAddress <https://eth-typing.readthedocs.io/en/latest/types.html#checksumaddress>`__.  # noqa: E501
        """

        return self._address
