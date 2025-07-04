# @version 0.4.0

# @dev Emitted when number is changed.
#
# `newNum` is the new number from the call.
# Expected every time number changes.
event NumberChange:
    b: bytes32
    prevNum: uint256
    dynData: String[12]
    newNum: indexed(uint256)
    dynIndexed: indexed(String[12])

event AddressChange:
    newAddress: indexed(address)

event FooHappened:
    foo: indexed(uint256)

event BarHappened:
    bar: indexed(uint256)

event EventWithStruct:
    a_struct: MyStruct

event EventWithAddressArray:
    some_id: uint256
    some_address: address
    participants: DynArray[address, 1024]
    agents: address[1]

event EventWithUintArray:
    agents: uint256[1]

# @dev This is the doc for MyStruct
struct MyStruct:
    a: address
    b: bytes32
    c: uint256

struct NestedStruct1:
    t: MyStruct
    foo: uint256

struct NestedStruct2:
    foo: uint256
    t: MyStruct

struct WithArray:
    foo: uint256
    arr: MyStruct[2]
    bar: uint256

struct IntStruct:
    one: uint256
    two: uint256
    three: uint256
    four: uint256
    five: uint256
    six: uint256

owner: public(address)
myNumber: public(uint256)
prevNumber: public(uint256)
theAddress: public(address)
balances: public(HashMap[address, uint256])
dynArray: public(DynArray[uint256, 3][3])
mixedArray: public(DynArray[DynArray[uint256, 3][3], 3][5])
arraysLoaded: bool
myStruct: public(MyStruct)
myBytes32: public(bytes32)

MAX_FOO : constant(uint256) = 5

@deploy
def __init__(num: uint256):
    self.myNumber = num
    self.owner = msg.sender
    self.arraysLoaded = False

@external
def fooAndBar():
    log FooHappened(0)
    log BarHappened(1)

@external
def setNumber(num: uint256):
    """
    @notice Sets a new number, with restrictions and event emission
    @dev Only the owner can call this function. The new number cannot be 5.
    @param num The new number to be set
    @custom:require num Must not be equal to 5
    @custom:modifies Sets the `myNumber` state variable
    @custom:emits Emits a `NumberChange` event with the previous number, the new number, and the previous block hash
    """
    assert msg.sender == self.owner, "!authorized"
    assert num != 5
    self.prevNumber = self.myNumber
    self.myNumber = num
    log NumberChange(block.prevhash, self.prevNumber, "Dynamic", num, "Dynamic")

@external
def setAddress(_address: address):
    self.theAddress = _address
    log AddressChange(_address)

@external
def setBytes32(val: bytes32):
    self.myBytes32 = val

@external
def setBalance(_address: address, bal: uint256):
    self.balances[_address] += bal

@view
@external
def getStruct() -> MyStruct:
    return MyStruct(a=msg.sender, b=block.prevhash, c=244)

@view
@external
def getNestedStruct1() -> NestedStruct1:
    return NestedStruct1(t=MyStruct(a=msg.sender, b=block.prevhash, c=244), foo=1)

@view
@external
def getNestedStruct2() -> NestedStruct2:
    return NestedStruct2(foo=2, t=MyStruct(a=msg.sender, b=block.prevhash, c=244))

@view
@external
def getNestedStructWithTuple1() -> (NestedStruct1, uint256):
    return (NestedStruct1(t=MyStruct(a=msg.sender, b=block.prevhash, c=244), foo=1), 1)

@view
@external
def getNestedStructWithTuple2() -> (uint256, NestedStruct2):
    return (2, NestedStruct2(foo=2, t=MyStruct(a=msg.sender, b=block.prevhash, c=244)))

@pure
@external
def getEmptyDynArrayOfStructs() -> DynArray[MyStruct, 10]:
    _my_structs: DynArray[MyStruct, 10] = []
    return _my_structs

@pure
@external
def getEmptyTupleOfDynArrayStructs() -> (DynArray[MyStruct, 10], DynArray[MyStruct, 10]):
    _my_structs_0: DynArray[MyStruct, 10] = []
    _my_structs_1: DynArray[MyStruct, 10] = []
    return (_my_structs_0, _my_structs_1)

@view
@external
def getEmptyTupleOfArrayOfStructsAndDynArrayOfStructs() -> (MyStruct[3], DynArray[MyStruct, 2]):
    _my_structs_0: MyStruct[3] = empty(MyStruct[3])
    _my_structs_1: DynArray[MyStruct, 2] = []
    return (_my_structs_0, _my_structs_1)

@view
@external
def getTupleOfIntAndStructArray() -> (uint256, IntStruct[MAX_FOO]):
    result : IntStruct[MAX_FOO] = empty(IntStruct[MAX_FOO])
    return 0, result

@pure
@external
def getEmptyTupleOfIntAndDynArray() -> (DynArray[uint256, 10], DynArray[MyStruct, 10]):
    _integers: DynArray[uint256, 10] = []
    _my_structs: DynArray[MyStruct, 10] = []
    return _integers, _my_structs

@view
@external
def getStructWithArray() -> WithArray:
    return WithArray(
        foo=1,
        arr=[
            MyStruct(a=msg.sender, b=block.prevhash, c=244),
            MyStruct(a=msg.sender, b=block.prevhash, c=244)
        ],
        bar=2
    )

@pure
@external
def getEmptyArray() -> DynArray[uint256, 1]:
    return []

@pure
@external
def getSingleItemArray() -> DynArray[uint256, 1]:
    return [1]

@pure
@external
def getFilledArray() -> DynArray[uint256, 3]:
    return [1, 2, 3]

@view
@external
def getAddressArray() -> DynArray[address, 2]:
    return [msg.sender, msg.sender]

@view
@external
def getDynamicStructArray() -> DynArray[NestedStruct1, 2]:
    return [
        NestedStruct1(t=MyStruct(a=msg.sender, b=block.prevhash, c=244), foo=1),
        NestedStruct1(t=MyStruct(a=msg.sender, b=block.prevhash, c=244), foo=2)
    ]

@view
@external
def getStaticStructArray() -> NestedStruct2[2]:
    return [
        NestedStruct2(foo=1, t=MyStruct(a=msg.sender, b=block.prevhash, c=244)),
        NestedStruct2(foo=2, t=MyStruct(a=msg.sender, b=block.prevhash, c=244))
    ]

@pure
@external
def getArrayWithBiggerSize() -> uint256[20]:
    return empty(uint256[20])


@pure
@external
def getTupleOfArrays() -> (uint256[20], uint256[20]):
    return (empty(uint256[20]), empty(uint256[20]))

@pure
@external
def getMultipleValues() -> (uint256, uint256):
    return (123, 321)

@pure
@external
def getUnnamedTuple() -> (uint256, uint256):
    return (0, 0)

@view
@external
def getTupleOfAddressArray() -> (address[20], uint128[20]):
    addresses: address[20] = empty(address[20])
    addresses[0] = msg.sender
    return (addresses, empty(uint128[20]))

@view
@external
def getNestedArrayFixedFixed() -> uint256[2][3]:
    return [[1, 2], [3, 4], [5, 6]]

@view
@external
def getNestedArrayDynamicFixed() -> DynArray[uint256[2], 1024]:
    return [[1, 2], [3, 4], [5, 6]]

@view
@external
def getNestedArrayFixedDynamic() -> DynArray[uint256, 1024][3]:
    return self.dynArray

@view
@external
def getNestedArrayMixedDynamic() -> DynArray[DynArray[uint256, 1024][3], 1024][5]:
    return self.mixedArray

@view
@external
def getNestedAddressArray() -> DynArray[address[3], 1024]:
    return [[msg.sender, msg.sender, msg.sender], [empty(address), empty(address), empty(address)]]

@view
@external
def functionWithUniqueAmountOfArguments(
    a0: uint256,
    a1: uint256,
    a2: uint256,
    a3: uint256,
    a4: uint256,
    a5: uint256,
    a6: uint256,
    a7: uint256,
    a8: uint256,
    a9: uint256
):
    pass

@external
def functionWithCalldata(data: Bytes[1_024]=b""):
    pass

@external
def setStruct(_my_struct: MyStruct):
    self.myStruct= _my_struct

@pure
@external
def setStructArray(_my_struct_array: MyStruct[2]):
    pass

@external
def logStruct():
    _bytes: bytes32 = 0x1234567890abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    _struct: MyStruct = MyStruct(
        a=msg.sender,
        b=_bytes,
        c=244
    )
    log EventWithStruct(_struct)

@external
def logAddressArray():
    ppl: DynArray[address, 1024] = []
    ppl.append(msg.sender)
    agts: address[1] = [msg.sender]
    log EventWithAddressArray(1001, msg.sender, ppl, agts)

@external
def logUintArray():
    agts: uint256[1] = [1]
    log EventWithUintArray(agts)

@external
def loadArrays():
    if not self.arraysLoaded:
        self.dynArray[0] = [0]
        self.dynArray[1] = [0, 1]
        self.dynArray[2] = [0, 1, 2]
        self.mixedArray[0].append(self.dynArray)
        self.mixedArray[1].append(self.dynArray)
        self.mixedArray[1].append(self.dynArray)
        self.arraysLoaded = True

@view
@external
def callThatReverts():
    assert False, "call revert"
