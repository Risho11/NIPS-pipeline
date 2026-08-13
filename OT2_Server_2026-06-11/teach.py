import sys
sys.path.append("/var/lib/jupyter/notebooks/2025-07-02/lib")
from arm import Arm

xArm = Arm(home=False)

xArm.clean()
xArm.teach()
