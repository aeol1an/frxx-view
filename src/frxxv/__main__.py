"""
python -m frxxv          → launches empty
python -m frxxv --demo   → launches with test figures
"""
import sys
from frxxv.app import main

main(demo="--demo" in sys.argv)