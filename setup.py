#!/usr/bin/env python
import re
from pathlib import Path

from setuptools import find_packages, setup

_HERE = Path(__file__).parent.absolute()
_CORE_PLUGIN_PATTERN = re.compile(r"\bape_\w+(?!\S)")
_PACKAGES = find_packages("src")
_MODULES = {p for p in _PACKAGES if re.match(_CORE_PLUGIN_PATTERN, p)}
_MODULES.add("ape")

extras_require = {
    "test": [  # `test` GitHub Action jobs uses this
        "pytest-xdist>=3.6.1,<4",  # Multi-process runner
        "pytest-cov>=4.0.0,<5",  # Coverage analyzer plugin
        "pytest-mock",  # For creating mocks
        "pytest-benchmark",  # For performance tests
        "pytest-rerunfailures",  # For flakey tests
        "pytest-timeout>=2.2.0,<3",  # For avoiding timing out during tests
        "hypothesis>=6.2.0,<7.0",  # Strategy-based fuzzer
        "hypothesis-jsonschema==0.19.0",  # JSON Schema fuzzer extension
        "ape-vyper>=0.8.9,<0.9",  # Needed for compiling test contracts
        "vyper>=0.4.3,<0.5",  # Avoid having to download Vyper binaries
        "ape-solidity>=0.8.5,<0.9",  # Needed for compiling test contracts
    ],
    "lint": [
        "ruff>=0.12.0",  # Unified linter and formatter
        "mypy>=1.16.1,<1.17.0",  # Static type analyzer
        "types-PyYAML",  # Needed due to mypy typeshed
        "types-requests",  # Needed due to mypy typeshed
        "types-setuptools",  # Needed due to mypy typeshed
        "pandas-stubs>=2.2.1.240316",  # Needed due to mypy typeshed
        "types-toml",  # Needed due to mypy typeshed
        "types-SQLAlchemy>=1.4.49",  # Needed due to mypy typeshed
        "types-python-dateutil",  # Needed due to mypy typeshed
        "mdformat>=0.7.22",  # Auto-formatter for markdown
        "mdformat-gfm>=0.3.5",  # Needed for formatting GitHub-flavored markdown
        "mdformat-frontmatter>=0.4.1",  # Needed for frontmatters-style headers in issue templates
        "mdformat-pyproject>=0.0.2",  # Allows configuring in pyproject.toml
    ],
    "doc": ["sphinx-ape"],
    "release": [  # `release` GitHub Action job uses this
        "setuptools>=75",  # Installation tool
        "wheel",  # Packaging tool
        "twine==3.8.0",  # Package upload tool
    ],
    "dev": [
        "commitizen>=2.40,<2.41",  # Semantic commit linting
        "pre-commit",  # Ensure that linters are run prior to committing
        "pytest-watch",  # `ptw` test watcher/runner
        "ipdb",  # Debugger (Must use `export PYTHONBREAKPOINT=ipdb.set_trace`)
    ],
    # NOTE: These are extras that someone can install to get up and running quickly w/ ape
    #       They should be kept up to date with what works and what doesn't out of the box
    #       Usage example: `pipx install eth-ape[recommended-plugins]`
    "recommended-plugins": (_HERE / "recommended-plugins.txt").read_text().splitlines(),
}

# NOTE: `pip install -e .[dev]` to install package
extras_require["dev"] = (
    extras_require["test"]
    + extras_require["lint"]
    + extras_require["doc"]
    + extras_require["release"]
    + extras_require["dev"]
    # NOTE: Do *not* install `recommended-plugins` w/ dev
)

long_description = Path("./README.md").read_text()


setup(
    name="eth-ape",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    description="Ape Ethereum Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ApeWorX Ltd.",
    author_email="admin@apeworx.io",
    url="https://apeworx.io",
    project_urls={
        "Documentation": "https://docs.apeworx.io/ape/",
        "Funding": "https://gitcoin.co/grants/5958/ape-maintenance-fund",
        "Source": "https://github.com/ApeWorX/ape",
        "Tracker": "https://github.com/ApeWorX/ape/issues",
        "Twitter": "https://twitter.com/ApeFramework",
    },
    include_package_data=True,
    install_requires=[
        "click>=8.1.6,<8.2",
        "ijson>=3.1.4,<4",
        "ipython>=8.18.1,<9",
        "lazyasd>=0.1.4",
        "asttokens>=2.4.1,<3",  # Peer dependency; w/o pin container build fails.
        "cchecksum>=0.0.3,<1",
        # Pandas peer-dep: Numpy 2.0 causes issues for some users.
        "numpy<2",
        "packaging>=23.0,<24",
        "pandas>=2.2.2,<3",
        "pluggy>=1.3,<2",
        "pydantic>=2.10.0,<3",
        "pydantic-settings>=2.5.2,<3",
        "pytest>=8.0,<9.0",
        "python-dateutil>=2.8.2,<3",
        "PyYAML>=5.1,<7",
        "requests>=2.28.1,<3",
        "rich>=13.9,<14",
        "SQLAlchemy>=1.4.35",
        "toml; python_version<'3.11'",
        "tqdm>=4.67,<5.0",
        "traitlets>=5.3.0",
        "urllib3>=2.3,<3",
        "watchdog>=3.0,<4",
        # ** Dependencies maintained by Ethereum Foundation **
        "eth-abi>=5.1.0,<6",
        "eth-account>=0.11.3,<0.14",
        "eth-typing>=3.5.2,<6",
        "eth-utils>=2.1.0,<6",
        "hexbytes>=0.3.1,<2",
        "py-geth>=5.4.0,<6",
        "trie>=3.0.1,<4",  # Peer: stricter pin needed for uv support.
        "web3[tester]>=6.20.1,<8",
        # ** Dependencies maintained by ApeWorX **
        "eip712>=0.2.10,<0.3",
        "ethpm-types>=0.6.27,<0.7",
        "eth_pydantic_types>=0.2.1,<0.3",
        "evmchains>=0.1.0,<0.2",
        "evm-trace>=0.2.6,<0.3",
    ],
    entry_points={
        "console_scripts": ["ape=ape._cli:cli"],
        "pytest11": ["ape_test=ape.pytest.plugin"],
        "ape_cli_subcommands": [
            "ape_accounts=ape_accounts._cli:cli",
            "ape_cache=ape_cache._cli:cli",
            "ape_compile=ape_compile._cli:cli",
            "ape_console=ape_console._cli:cli",
            "ape_plugins=ape_plugins._cli:cli",
            "ape_run=ape_run._cli:cli",
            "ape_networks=ape_networks._cli:cli",
            "ape_test=ape_test._cli:cli",
            "ape_init=ape_init._cli:cli",
            "ape_pm=ape_pm._cli:cli",
        ],
    },
    python_requires=">=3.9,<4",
    extras_require=extras_require,
    py_modules=list(_MODULES),
    license="Apache-2.0",
    zip_safe=False,
    keywords="ethereum",
    packages=_PACKAGES,
    package_dir={"": "src"},
    package_data={p: ["py.typed"] for p in _MODULES},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: MacOS",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)
