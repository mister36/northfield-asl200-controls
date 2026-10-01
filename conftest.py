def pytest_addoption(parser):
    parser.addoption("--variant", action="append", default=None, help="limit the SIL matrix to these variants")
    parser.addoption("--scenario", action="append", default=None, help="limit the SIL matrix to these scenarios")
