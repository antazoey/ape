from collections.abc import Iterable, Iterator, Sequence
from functools import cached_property
from typing import TYPE_CHECKING, Any, Optional, Union

from eth_pydantic_types import HexBytes, HexStr
from eth_utils import encode_hex, is_hex, keccak, to_hex
from ethpm_types.abi import EventABI
from pydantic import BaseModel, field_serializer, field_validator, model_validator
from web3.types import FilterParams

from ape.exceptions import ContractNotFoundError
from ape.types.address import AddressType
from ape.types.basic import HexInt
from ape.utils.abi import LogInputABICollection, encode_topics
from ape.utils.basemodel import BaseInterfaceModel, ExtraAttributesMixin, ExtraModelAttributes
from ape.utils.misc import ZERO_ADDRESS, log_instead_of_fail

if TYPE_CHECKING:
    from ape.api.providers import BlockAPI
    from ape.contracts import ContractEvent


TopicFilter = Sequence[Union[Optional[HexStr], Sequence[Optional[HexStr]]]]


class LogFilter(BaseModel):
    addresses: list[AddressType] = []
    events: list[EventABI] = []
    topic_filter: TopicFilter = []
    start_block: int = 0
    stop_block: Optional[int] = None  # Use block height
    selectors: dict[str, EventABI] = {}

    @model_validator(mode="before")
    @classmethod
    def compute_selectors(cls, values):
        values["selectors"] = {
            encode_hex(keccak(text=event.selector)): event for event in values.get("events") or []
        }

        return values

    @field_validator("start_block", mode="before")
    @classmethod
    def validate_start_block(cls, value):
        return value or 0

    @field_validator("addresses", "events", "topic_filter", mode="before")
    @classmethod
    def _convert_none_to_empty_list(cls, value):
        return value or []

    @field_validator("selectors", mode="before")
    @classmethod
    def _convert_none_to_dict(cls, value):
        return value or {}

    def model_dump(self, *args, **kwargs):
        return FilterParams(
            address=self.addresses,
            fromBlock=to_hex(self.start_block),
            toBlock=to_hex(self.stop_block or self.start_block),
            topics=self.topic_filter,  # type: ignore
        )

    @classmethod
    def from_event(
        cls,
        event: Union[EventABI, "ContractEvent"],
        search_topics: Optional[dict[str, Any]] = None,
        addresses: Optional[list[AddressType]] = None,
        start_block=None,
        stop_block=None,
    ):
        """
        Construct a log filter from an event topic query.
        """
        abi = getattr(event, "abi", event)
        topic_filter = encode_topics(abi, search_topics or {})
        return cls(
            addresses=addresses or [],
            events=[abi],
            topic_filter=topic_filter,
            start_block=start_block,
            stop_block=stop_block,
        )


class BaseContractLog(BaseInterfaceModel):
    """
    Base class representing information relevant to an event instance.
    """

    event_name: str
    """The name of the event."""

    contract_address: AddressType = ZERO_ADDRESS
    """The contract responsible for emitting the log."""

    event_arguments: dict[str, Any] = {}
    """The arguments to the event, including both indexed and non-indexed data."""

    def __eq__(self, other: Any) -> bool:
        if self.contract_address != other.contract_address or self.event_name != other.event_name:
            return False

        for k, v in self.event_arguments.items():
            other_v = other.event_arguments.get(k)
            if v != other_v:
                return False

        return True

    @field_serializer("event_arguments")
    def _serialize_event_arguments(self, event_arguments, info):
        """
        Because of an issue with BigInt in Pydantic,
        (https://github.com/pydantic/pydantic/issues/10152)
        we have to ensure these are regular ints.
        """
        return self._serialize_value(event_arguments, info)

    def _serialize_value(self, value: Any, info) -> Any:
        if isinstance(value, int):
            # Handle custom ints.
            return int(value)

        elif isinstance(value, HexBytes):
            return to_hex(value) if info.mode == "json" else value

        elif isinstance(value, str):
            # Avoiding str triggering iterable condition.
            return value

        elif isinstance(value, dict):
            # Also, avoid handling dict in the iterable case.
            return {k: self._serialize_value(v, info) for k, v in value.items()}

        elif isinstance(value, Iterable):
            return [self._serialize_value(v, info) for v in value]

        return value


# TODO: In 0.9, make this correctly serialize back to log data you get from RPCs.
class ContractLog(ExtraAttributesMixin, BaseContractLog):
    """
    An instance of a log from a contract.
    """

    def __init__(self, *args, **kwargs):
        abi = kwargs.pop("_abi", None)
        super().__init__(*args, **kwargs)
        if isinstance(abi, LogInputABICollection):
            abi = abi.abi

        self._abi = abi

    transaction_hash: Any
    """The hash of the transaction containing this log."""

    block_number: HexInt
    """The number of the block containing the transaction that produced this log."""

    block_hash: Any
    """The hash of the block containing the transaction that produced this log."""

    log_index: HexInt
    """The index of the log on the transaction."""

    transaction_index: Optional[HexInt] = None
    """
    The index of the transaction's position when the log was created.
    Is `None` when from the pending block.
    """

    @field_validator("transaction_hash", mode="before")
    @classmethod
    def _validate_transaction_hash(cls, transaction_hash):
        if (
            isinstance(transaction_hash, str)
            and is_hex(transaction_hash)
            and not transaction_hash.startswith("0x")
        ):
            return f"0x{transaction_hash}"

        return transaction_hash

    @field_serializer("transaction_hash", "block_hash")
    def _serialize_hashes(self, value, info):
        return self._serialize_value(value, info)

    # NOTE: This class has an overridden `__getattr__` method, but `block` is a reserved keyword
    #       in most smart contract languages, so it is safe to use. Purposely avoid adding
    #       `.datetime` and `.timestamp` in case they are used as event arg names.
    @cached_property
    def block(self) -> "BlockAPI":
        return self.chain_manager.blocks[self.block_number]

    @property
    def abi(self) -> EventABI:
        """
        An ABI describing the event.
        """
        if abi := self._abi:
            return abi

        try:
            contract = self.chain_manager.contracts[self.contract_address]
        except (ContractNotFoundError, KeyError):
            pass

        else:
            for event_abi in contract.events:
                if event_abi.name == self.event_name and len(event_abi.inputs) == len(
                    self.event_arguments
                ):
                    abi = event_abi

        if abi is None:
            # Last case scenario, try to calculate it.
            # NOTE: This is a rare edge case that shouldn't really happen,
            #   so this is a lower priority.
            # TODO: Handle inputs here.
            abi = EventABI(name=self.event_name)

        self._abi = abi
        return abi

    @cached_property
    def topics(self) -> list[HexStr]:
        """
        The encoded hex-str topics values.
        """
        return encode_topics(self.abi, self.event_arguments)

    @property
    def timestamp(self) -> int:
        """
        The UNIX timestamp of when the event was emitted.

        NOTE: This performs a block lookup.
        """
        return self.block.timestamp

    @property
    def _event_args_str(self) -> str:
        return " ".join(f"{key}={val}" for key, val in self.event_arguments.items())

    def __str__(self) -> str:
        return f"{self.event_name}({self._event_args_str})"

    @log_instead_of_fail(default="<ContractLog>")
    def __repr__(self) -> str:
        event_arg_str = self._event_args_str
        suffix = f" {event_arg_str}" if event_arg_str else ""
        return f"<{self.event_name or 'Event'}{suffix}>"

    def __ape_extra_attributes__(self) -> Iterator[ExtraModelAttributes]:
        yield ExtraModelAttributes(
            name=self.event_name or "event",
            attributes=lambda: self.event_arguments or {},
            include_getattr=True,
            include_getitem=True,
        )

    def __contains__(self, item: str) -> bool:
        return item in self.event_arguments

    def __eq__(self, other: Any) -> bool:
        """
        Check for equality between this instance and another ContractLog instance.

        If the other object is not an instance of ContractLog, this method returns
        NotImplemented. This triggers the Python interpreter to call the __eq__ method
        on the other object (i.e., y.__eq__(x)) if it is defined, allowing for a custom
        comparison. This behavior is leveraged by the MockContractLog class to handle
        custom comparison logic between ContractLog and MockContractLog instances.

        Args:
            other (Any): The object to compare with this instance.

        Returns:
            bool: True if the two instances are equal, False otherwise.
        """

        if not isinstance(other, ContractLog):
            return NotImplemented

        # call __eq__ on parent class
        return super().__eq__(other)

    def get(self, item: str, default: Optional[Any] = None) -> Any:
        return self.event_arguments.get(item, default)


def _equal_event_inputs(mock_input: Any, real_input: Any) -> bool:
    if mock_input is None:
        # Check is skipped.
        return True

    elif isinstance(mock_input, (list, tuple)):
        if not isinstance(real_input, (list, tuple)) or len(real_input) != len(mock_input):
            return False

        return all(_equal_event_inputs(m, r) for m, r in zip(mock_input, real_input))

    else:
        return mock_input == real_input


class MockContractLog(BaseContractLog):
    """
    A mock version of the ContractLog class used for testing purposes.
    This class is designed to match a subset of event arguments in a ContractLog instance
    by only comparing those event arguments that the user explicitly provides.

    Inherits from :class:`~ape.types.BaseContractLog`, and overrides the
    equality method for custom comparison
    of event arguments between a MockContractLog and a ContractLog instance.
    """

    def __eq__(self, other: Any) -> bool:
        if (
            not hasattr(other, "contract_address")
            or not hasattr(other, "event_name")
            or self.contract_address != other.contract_address
            or self.event_name != other.event_name
        ):
            return False

        # NOTE: `self.event_arguments` contains a subset of items from `other.event_arguments`,
        #       but we skip those the user doesn't care to check
        for name, value in self.event_arguments.items():
            other_input = other.event_arguments.get(name)
            if not _equal_event_inputs(value, other_input):
                # Only exit on False; Else, keep checking.
                return False

        return True


class ContractLogContainer(list):
    """
    Container for ContractLogs which is adding capability of filtering logs
    """

    def filter(self, event: "ContractEvent", **kwargs) -> list[ContractLog]:
        return [
            x
            for x in self
            if x.event_name == event.name
            and x.contract_address == event.contract
            and all(v == x.event_arguments.get(k) and v is not None for k, v in kwargs.items())
        ]

    def __contains__(self, val: Any) -> bool:
        return any(log == val for log in self)
