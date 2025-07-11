import pytest
from ethpm_types import ContractType

from ape import Contract
from ape.contracts import ContractContainer, ContractInstance
from ape.exceptions import (
    ArgumentsLengthError,
    MethodNonPayableError,
    MissingDeploymentBytecodeError,
    NetworkError,
    ProjectError,
)
from ape_ethereum.ecosystem import ProxyType
from tests.conftest import explorer_test


def test_deploy(
    not_owner,
    contract_container,
    networks_connected_to_tester,
    clean_contract_caches,
):
    contract = contract_container.deploy(4, sender=not_owner, something_else="IGNORED")
    assert contract.txn_hash
    assert contract.myNumber() == 4

    # Verify can reload same contract from cache
    contract_from_cache = Contract(contract.address)
    assert contract_from_cache.contract_type == contract.contract_type
    assert contract_from_cache.address == contract.address
    assert contract_from_cache.txn_hash == contract.txn_hash


def test_deploy_wrong_number_of_arguments(
    not_owner,
    contract_container,
    networks_connected_to_tester,
    clean_contract_caches,
):
    expected = (
        r"The number of the given arguments \(0\) do not match what is defined in the "
        r"ABI:\n\n\t.*__init__\(uint256 num\).*"
    )
    with pytest.raises(ArgumentsLengthError, match=expected):
        contract_container.deploy(sender=not_owner)


def test_deploy_and_publish_local_network(owner, contract_container):
    with pytest.raises(ProjectError, match="Can only publish deployments on a live network"):
        contract_container.deploy(0, sender=owner, publish=True)


def test_deploy_and_publish_live_network_no_explorer(owner, contract_container, dummy_live_network):
    dummy_live_network.__dict__["explorer"] = None
    expected_message = "Unable to publish contract - no explorer plugin installed."
    with pytest.raises(NetworkError, match=expected_message):
        contract_container.deploy(0, sender=owner, publish=True, required_confirmations=0)


@explorer_test
def test_deploy_and_publish(
    owner, contract_container, dummy_live_network_with_explorer, mock_explorer
):
    contract = contract_container.deploy(0, sender=owner, publish=True, required_confirmations=0)
    mock_explorer.publish_contract.assert_called_once_with(contract.address)


@explorer_test
def test_deploy_and_not_publish(
    owner, contract_container, dummy_live_network_with_explorer, mock_explorer
):
    contract_container.deploy(0, sender=owner, publish=False, required_confirmations=0)
    assert not mock_explorer.call_count


def test_deploy_privately(owner, contract_container):
    deploy_0 = owner.deploy(contract_container, 3, private=True)
    assert isinstance(deploy_0, ContractInstance)

    deploy_1 = contract_container.deploy(3, sender=owner, private=True)
    assert isinstance(deploy_1, ContractInstance)


@pytest.mark.parametrize("bytecode", (None, {}, {"bytecode": "0x"}))
def test_deploy_no_deployment_bytecode(owner, bytecode):
    """
    https://github.com/ApeWorX/ape/issues/1904
    """
    expected = (
        r"Cannot deploy: contract 'Apes' has no deployment-bytecode\. "
        r"Are you attempting to deploy an interface\?"
    )
    contract_type = ContractType.model_validate(
        {"abi": [], "contractName": "Apes", "deploymentBytecode": bytecode}
    )
    contract = ContractContainer(contract_type)
    with pytest.raises(MissingDeploymentBytecodeError, match=expected):
        contract.deploy(sender=owner)


def test_deploy_sending_funds_to_non_payable_constructor(project, owner):
    with pytest.raises(
        MethodNonPayableError,
        match=r"Sending funds to a non-payable constructor\.",
    ):
        project.SolidityContract.deploy(1, sender=owner, value="1 ether")


def test_deployments(owner, eth_tester_provider, project):
    initial_deployed_contract = project.VyperContract.deploy(10000000, sender=owner)
    actual = project.VyperContract.deployments[-1].address
    expected = initial_deployed_contract.address
    assert actual == expected


def test_deploy_proxy(owner, vyper_contract_instance, project, chain, eth_tester_provider):
    target = vyper_contract_instance.address
    proxy = project.SimpleProxy.deploy(target, sender=owner)

    # Ensure we can call both proxy and target methods on it.
    assert proxy.implementation  # No attr err
    assert proxy.myNumber  # No attr err

    # Ensure caching works.
    assert proxy.address in chain.contracts.contract_types
    assert proxy.address in chain.contracts.proxy_infos

    # Show the cached proxy info is correct.
    proxy_info = chain.contracts.proxy_infos[proxy.address]
    assert proxy_info.target == target
    assert proxy_info.type == ProxyType.Delegate

    # Show we get the implementation contract type using the proxy address
    re_contract = chain.contracts.instance_at(proxy.address)
    assert re_contract.contract_type == proxy.contract_type

    # Show proxy methods are not available on target alone.
    target = chain.contracts.instance_at(proxy_info.target)
    assert target.myNumber  # No attr err
    with pytest.raises(AttributeError):
        _ = target.implementation


def test_source_path_in_project(project_with_contract):
    contract = project_with_contract.contracts["Contract"]
    contract_container = project_with_contract.get_contract("Contract")
    expected = project_with_contract.path / contract.source_id
    assert contract_container.source_path.is_file()
    assert contract_container.source_path == expected


def test_source_path_out_of_project(solidity_contract_instance, project):
    solidity_contract_instance.base_path = None
    with project.isolate_in_tempdir(chdir=True):
        assert not solidity_contract_instance.source_path


def test_encode_constructor_input(contract_container, calldata):
    constructor = contract_container.constructor
    actual = constructor.encode_input(222)
    expected = calldata[4:]  # Strip off setNumber() method ID
    assert actual == expected


def test_decode_constructor_input(contract_container, calldata):
    constructor = contract_container.constructor
    constructor_calldata = calldata[4:]  # Strip off setNumber() method ID
    actual = constructor.decode_input(constructor_calldata)
    expected = "constructor(uint256)", {"num": 222}
    assert actual == expected


def test_decode_input(contract_container, calldata):
    actual = contract_container.decode_input(calldata)
    expected = "setNumber(uint256)", {"num": 222}
    assert actual == expected


def test_declare(contract_container, sender):
    receipt = contract_container.declare(sender=sender)
    assert not receipt.failed


def test_source_id(contract_container):
    actual = contract_container.source_id
    expected = contract_container.contract_type.source_id
    # Is just a pass-through (via extras-model), but making sure it works.
    assert actual == expected


def test_at(vyper_contract_instance, project):
    instance = project.VyperContract.at(vyper_contract_instance.address)
    assert instance == vyper_contract_instance


def test_at_fetch_from_explorer_false(
    project_with_contract, mock_explorer, eth_tester_provider, owner
):
    # Grab the container - note: this always compiles!
    container = project_with_contract.Contract
    instance = container.deploy(sender=owner)

    # Hack off the fact that it was compiled.
    project_with_contract.clean()

    # Simulate having an explorer plugin installed (e.g. ape-etherscan).
    eth_tester_provider.network.__dict__["explorer"] = mock_explorer

    # Attempt to create an instance. It should NOT use the explorer at all!
    instance2 = container.at(instance.address, fetch_from_explorer=False)

    assert instance == instance2
    # Ensure explorer was not used at all.
    assert mock_explorer.get_contract_type.call_count == 0

    # Clean up test.
    eth_tester_provider.network.__dict__.pop("explorer")
