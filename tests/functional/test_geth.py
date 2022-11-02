# def test_get_call_tree_erigon(mock_web3, geth_provider, trace_response):
#     mock_web3.client_version = "erigon_MOCK"
#     mock_web3.provider.make_request.return_value = trace_response
#     result = geth_provider.get_call_tree(TRANSACTION_HASH)
#     actual = repr(result)
#     expected = "CALL: 0xC17f2C69aE2E66FD87367E3260412EEfF637F70E.<0x96d373e5> [1401584 gas]"
#     assert expected in actual
#
#
# def test_repr_on_local_network_and_disconnected(networks):
#     geth = networks.get_provider_from_choice("ethereum:local:geth")
#     assert repr(geth) == "<geth>"
#
#
# def test_repr_on_live_network_and_disconnected(networks):
#     geth = networks.get_provider_from_choice("ethereum:goerli:geth")
#     assert repr(geth) == "<geth chain_id=5>"
#
#
# def test_repr_connected(mock_web3, geth_provider):
#     mock_web3.eth.chain_id = 123
#     assert repr(geth_provider) == "<geth chain_id=123>"
#
#
# test_get_logs_when_connected_to_geth(vyper_contract_instance, eth_tester_provider_geth, owner):
#     vyper_contract_instance.setNumber(123, sender=owner)
#     actual = vyper_contract_instance.NumberChange[-1]
#     assert actual.event_name == "NumberChange"
#     assert actual.contract_address == vyper_contract_instance.address
#     assert actual.event_arguments["newNum"] == 123
#
#
# def test_chain_id_when_connected(eth_tester_provider_geth):
#     assert eth_tester_provider_geth.chain_id == 131277322940537
#
#
# def test_chain_id_live_network_not_connected(networks):
#     geth = networks.get_provider_from_choice("ethereum:goerli:geth")
#     assert geth.chain_id == 5
#
#
# def test_chain_id_live_network_connected_uses_web3_chain_id(mocker, eth_tester_provider_geth):
#     mock_network = mocker.MagicMock()
#     mock_network.chain_id = 999999999  # Shouldn't use hardcoded network
#     orig_network = eth_tester_provider_geth.network
#     eth_tester_provider_geth.network = mock_network
#
#     # Still use the connected chain ID instead network's
#     assert eth_tester_provider_geth.chain_id == 131277322940537
#     eth_tester_provider_geth.network = orig_network
#
#
# def test_connect_wrong_chain_id(mocker, ethereum, eth_tester_provider_geth):
#     eth_tester_provider_geth.network = ethereum.get_network("goerli")
#
#     # Ensure when reconnecting, it does not use HTTP
#     factory = mocker.patch("ape_geth.provider._create_web3")
#     factory.return_value = eth_tester_provider_geth._web3
#
#     expected_error_message = (
#         "Provider connected to chain ID '131277322940537', "
#         "which does not match network chain ID '5'. "
#         "Are you connected to 'goerli'?"
#     )
#     with pytest.raises(NetworkMismatchError, match=expected_error_message):
#         eth_tester_provider_geth.connect()
#
#
# def test_supports_tracing(eth_tester_provider_geth):
#     assert eth_tester_provider_geth.supports_tracing
#
#
# @pytest.mark.parametrize("block_id", (0, "0", "0x0", HexStr("0x0")))
# def test_get_block(eth_tester_provider_geth, block_id):
#     block = cast(Block, eth_tester_provider_geth.get_block(block_id))
#
#     # Each parameter is the same as requesting the first block.
#     assert block.number == 0
#     assert block.base_fee == 1000000000
#     assert block.gas_used == 0
#
#
# def test_get_block_not_found(eth_tester_provider_geth):
#     latest_block = eth_tester_provider_geth.get_block("latest")
#     block_id = latest_block.number + 1000
#     with pytest.raises(BlockNotFoundError, match=f"Block with ID '{block_id}' not found."):
#         eth_tester_provider_geth.get_block(block_id)
#
#
# def test_get_receipt_not_exists_with_timeout(eth_tester_provider_geth):
#     unknown_txn = TRANSACTION_HASH
#     with pytest.raises(TransactionNotFoundError, match=f"Transaction '{unknown_txn}' not found"):
#         eth_tester_provider_geth.get_receipt(unknown_txn, timeout=0)
#
#
# def test_get_receipt(vyper_contract_instance, eth_tester_provider_geth, owner):
#     receipt = vyper_contract_instance.setNumber(123, sender=owner)
#     actual = eth_tester_provider_geth.get_receipt(receipt.txn_hash)
#     assert receipt.txn_hash == actual.txn_hash
#     assert actual.receiver == vyper_contract_instance.address
#     assert actual.sender == receipt.sender
