import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from app.core.db import Base

print(Base.metadata.tables.keys())
