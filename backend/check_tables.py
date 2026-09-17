import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from app.core.db import Base
from app.models import models
print(Base.metadata.tables.keys())
