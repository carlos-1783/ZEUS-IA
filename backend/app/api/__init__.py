"""
API package initialization.
This file makes the api directory a Python package.
"""

# Import the router from v1 to make it available at the package level
from .v1 import api_router

__all__ = ['api_router']
