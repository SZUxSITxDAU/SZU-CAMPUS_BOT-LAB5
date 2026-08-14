import os, sys, unittest
from pathlib import Path
root = Path(os.environ["CAMPUSBOT_SOURCE_ROOT"])
sys.path.insert(0, str(root))
suite = unittest.defaultTestLoader.discover(str(root / "tests"), "test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
