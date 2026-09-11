"""Executa la suite de proves de Sevalor Suite."""

import os
import sys

# Activar mode de testing per a NullPool i aïllament d'event loops
os.environ["TESTING"] = "1"

import unittest  # noqa: E402

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(not result.wasSuccessful())
