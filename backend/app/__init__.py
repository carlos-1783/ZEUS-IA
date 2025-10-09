"""
Application package initialization.
This file makes the app directory a Python package.
"""

# Import the router from v1 to make it available at the package level
from .api.v1 import api_router

__all__ = ['api_router']
