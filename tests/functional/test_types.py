from typing import Any, Optional

import pytest
from eth_utils import to_hex
from ethpm_types.abi import EventABI
from hexbytes import HexBytes
from pydantic import BaseModel, Field, ValidationError

from ape.types.address import AddressType
from ape.types.basic import HexInt
from ape.types.events import ContractLog, LogFilter
from ape.types.private_mempool import SimulationReport
from ape.types.units import CurrencyValueComparable
from ape.utils.misc import ZERO_ADDRESS

TXN_HASH = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa222222222222222222222222"
BLOCK_HASH = "0x999999998d4f99f68db9999999999da27ed049458b139999999999e910155b99"
BLOCK_NUMBER = 323423
EVENT_NAME = "MyEvent"
LOG_INDEX = 7
TXN_INDEX = 2
RAW_LOG: dict = {
    "block_hash": BLOCK_HASH,
    "block_number": BLOCK_NUMBER,
    "contract_address": ZERO_ADDRESS,
    "event_arguments": {"foo": 0, "bar": 1},
    "log_index": LOG_INDEX,
    "event_name": EVENT_NAME,
    "transaction_hash": TXN_HASH,
    "transaction_index": TXN_INDEX,
}
RAW_EVENT_ABI = """
{
  "anonymous": false,
  "inputs": [
    {
      "indexed": true,
      "name": "oldVersion",
      "type": "address"
    },
    {
      "indexed": true,
      "name": "newVersion",
      "type": "address"
    }
  ],
  "name": "StrategyMigrated",
  "type": "event"
}
"""


@pytest.fixture
def log():
    return ContractLog(**RAW_LOG)


def test_contract_log_serialization(log, zero_address):
    obj = ContractLog.model_validate(log.model_dump())
    assert obj.contract_address == zero_address
    assert obj.block_hash == BLOCK_HASH
    assert obj.block_number == BLOCK_NUMBER
    assert obj.event_name == EVENT_NAME
    assert obj.log_index == 7
    assert obj.transaction_hash == TXN_HASH
    assert obj.transaction_index == TXN_INDEX


def test_contract_log_serialization_with_hex_strings_and_non_checksum_addresses(log, zero_address):
    data = log.model_dump()
    data["log_index"] = to_hex(log.log_index)
    data["transaction_index"] = to_hex(log.transaction_index)
    data["block_number"] = to_hex(log.block_number)
    data["contract_address"] = log.contract_address.lower()

    obj = ContractLog(**data)

    assert obj.contract_address == zero_address
    assert obj.block_hash == BLOCK_HASH
    assert obj.block_number == BLOCK_NUMBER
    assert obj.event_name == EVENT_NAME
    assert obj.log_index == 7
    assert obj.transaction_hash == TXN_HASH
    assert obj.transaction_index == TXN_INDEX


def test_contract_log_str(log):
    obj = ContractLog.model_validate(log.model_dump())
    assert str(obj) == "MyEvent(foo=0 bar=1)"


def test_contract_log_repr(log):
    obj = ContractLog.model_validate(log.model_dump())
    assert repr(obj) == "<MyEvent foo=0 bar=1>"


def test_contract_log_access(log):
    assert "foo" in log
    assert "bar" in log
    assert log.foo == log["foo"] == log.get("foo") == 0
    assert log.bar == log["bar"] == log.get("bar") == 1


def test_contract_log_abi(log):
    # The log fixture is very basic class usage.
    assert log.abi.name == "MyEvent"


def test_contract_log_topics(log):
    actual = log.topics
    expected = ["0x4dbfb68b43dddfa12b51ebe99ab8fded620f9a0ac23142879a4f192a1b7952d2"]
    assert actual == expected


def test_topic_filter_encoding():
    event_abi = EventABI.model_validate_json(RAW_EVENT_ABI)
    log_filter = LogFilter.from_event(
        event=event_abi, search_topics={"newVersion": "0x8c44Cc5c0f5CD2f7f17B9Aca85d456df25a61Ae8"}
    )
    assert log_filter.topic_filter == [
        "0x100b69bb6b504e1252e36b375233158edee64d071b399e2f81473a695fd1b021",
        None,
        "0x0000000000000000000000008c44cc5c0f5cd2f7f17b9aca85d456df25a61ae8",
    ]


def test_log_filter_model_validate_coerces_nones():
    log_filter = LogFilter.model_validate(
        {"addresses": None, "events": None, "topic_filter": None, "selectors": None}
    )
    assert log_filter.addresses == []
    assert log_filter.events == []
    assert log_filter.topic_filter == []
    assert log_filter.selectors == {}


def test_address_type(owner):
    class MyModel(BaseModel):
        addr: AddressType

    # Show str works.
    instance_str = MyModel(addr=owner.address)
    assert instance_str.addr == owner.address

    # Show hex bytes work.
    instance_hex_bytes = MyModel(addr=HexBytes(owner.address))
    assert instance_hex_bytes.addr == owner.address

    # Show raw bytes work.
    instance_bytes = MyModel(addr=bytes.fromhex(owner.address[2:]))
    assert instance_bytes.addr == owner.address

    # Show int works.
    instance_bytes = MyModel(addr=int(owner.address, 16))
    assert instance_bytes.addr == owner.address


class TestHexInt:
    def test_model(self):
        class MyModel(BaseModel):
            ual: HexInt = 0
            ual_optional: Optional[HexInt] = Field(default=None, validate_default=True)

        act = MyModel.model_validate({"ual": "0x123"})
        expected = 291  # Base-10 form of 0x123.
        assert act.ual == expected
        assert act.ual_optional is None

    def test_none(self):
        """
        Was getting unhelpful conversion errors here. We should instead
        let Pydantic fail as it normally does in this situation.
        """

        class MyModel(BaseModel):
            an_int: HexInt

        expected = ".*Input should be a valid integer.*"
        with pytest.raises(ValidationError, match=expected):
            _ = MyModel(an_int=None)


class TestCurrencyValueComparable:
    def test_use_for_int_in_pydantic_model(self):
        value = 100000000000000000000000000000000000000000000

        class MyBasicModel(BaseModel):
            val: int

        model = MyBasicModel.model_validate({"val": CurrencyValueComparable(value)})
        assert model.val == value

        # Ensure serializes.
        dumped = model.model_dump()
        assert dumped["val"] == value

    @pytest.mark.parametrize("mode", ("json", "python"))
    def test_use_in_model_annotation(self, mode):
        value = 100000000000000000000000000000000000000000000

        class MyAnnotatedModel(BaseModel):
            val: CurrencyValueComparable
            val_optional: Optional[CurrencyValueComparable]

        model = MyAnnotatedModel.model_validate({"val": value, "val_optional": value})
        assert isinstance(model.val, CurrencyValueComparable)
        assert model.val == value

        # Show can use currency-comparable
        expected_currency_value = "100000000000000000000000000 ETH"
        assert model.val == expected_currency_value
        assert model.val_optional == expected_currency_value

        # Ensure serializes.
        dumped = model.model_dump(mode=mode)
        assert dumped["val"] == value
        assert dumped["val_optional"] == value

    def test_validate_from_currency_value(self):
        class MyAnnotatedModel(BaseModel):
            val: CurrencyValueComparable
            val_optional: Optional[CurrencyValueComparable]
            val_in_dict: dict[str, Any]

        value = "100000000000000000000000000 ETH"
        expected = 100000000000000000000000000000000000000000000
        data = {
            "val": value,
            "val_optional": value,
            "val_in_dict": {"value": CurrencyValueComparable(expected)},
        }
        model = MyAnnotatedModel.model_validate(data)
        for actual in (model.val, model.val_optional, model.val_in_dict["value"]):
            for ex in (value, expected):
                assert actual == ex

    def test_hashable(self):
        mapping: dict[int, str] = {0: "0", 1: "1"}
        key = CurrencyValueComparable(0)
        assert key in mapping
        assert mapping[key] == "0"


class TestSimulationReport:
    def test_model(self):
        data = {
            "success": True,
            "stateBlock": "0xa",
            "mevGasPrice": "0x399339e8",
            "profit": "0x14537d8d4b310",
            "refundableValue": "0x14537d8d4b310",
            "gasUsed": "0x5a60a",
            "logs": [
                {
                    "txLogs": [
                        {
                            "address": "0x5fbdb2315678afecb367f032d93f642f64180aa3",
                            "topics": [
                                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                                "0x0000000000000000000000009fe46736679d2d9a65f0992f2272de9f3c7fa6e0",
                                "0x0000000000000000000000003c44cdddb6a900fa2b585dd299e03d12fa4293bc",
                            ],
                            "data": "0x00000000000000000000000000000000000000000000000000000000000186a0",
                            "blockHash": None,
                            "blockNumber": None,
                            "transactionHash": "0x52a4d4f8e0411d06aa5b9bc6ab0a143716225ca8f16568739f80c22d31b8f450",
                            "transactionIndex": "0x0",
                            "logIndex": "0x0",
                            "removed": False,
                        }
                    ]
                },
                {
                    "txLogs": [
                        {
                            "address": "0xe7f1725e7734ce288f8367e1bb143e90bb3f0512",
                            "topics": [
                                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                                "0x0000000000000000000000003c44cdddb6a900fa2b585dd299e03d12fa4293bc",
                                "0x0000000000000000000000009fe46736679d2d9a65f0992f2272de9f3c7fa6e0",
                            ],
                            "data": "0x00000000000000000000000000000000000000000000000000000000000186a0",
                            "blockHash": None,
                            "blockNumber": None,
                            "transactionHash": "0xf678d62c462dc5a63504e1703822dc6740771a8cd4b57bf74f660e50792e3c40",
                            "transactionIndex": "0x1",
                            "logIndex": "0x1",
                            "removed": False,
                        }
                    ]
                },
            ],
        }
        report = SimulationReport.model_validate(data)
        assert report.success

        event = EventABI.model_validate(
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "from", "type": "address"},
                    {"indexed": True, "name": "to", "type": "address"},
                    {"indexed": False, "name": "value", "type": "uint256"},
                ],
                "name": "Transfer",
                "type": "event",
            }
        )

        events = list(report.decode_logs(event))
        assert len(events) == 2
        assert events[0].event_name == "Transfer"
        assert events[1].event_name == "Transfer"
