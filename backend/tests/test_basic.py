"""
Basic tests for the application that don't require importing the full app.
These tests verify core functionality without database dependencies.
"""
import pytest
from unittest.mock import MagicMock, patch

# Test configuration
TEST_CONFIG = {
    "PROJECT_NAME": "TestApp",
    "VERSION": "1.0.0",
    "API_V1_STR": "/api/v1",
    "DEBUG": True,
    "ENV": "test"
}

# Mock the settings module
class MockSettings:
    def __init__(self, **kwargs):
        for key, value in {**TEST_CONFIG, **kwargs}.items():
            setattr(self, key, value)

# Apply the mock settings
@pytest.fixture(scope="module")
def mock_settings():
    with patch('app.core.config.settings', MockSettings()):
        yield

def test_mock_settings(mock_settings):
    """Test that our mock settings work as expected"""
    from app.core.config import settings
    assert settings.PROJECT_NAME == "TestApp"
    assert settings.DEBUG is True
    assert settings.ENV == "test"

# Test the lifespan context manager
@pytest.mark.asyncio
async def test_lifespan():
    """Test the lifespan context manager functionality"""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    
    startup_complete = False
    
    @asynccontextmanager
    async def test_lifespan_wrapper(app):
        nonlocal startup_complete
        startup_complete = True
        yield
        startup_complete = False
    
    test_app = FastAPI(lifespan=test_lifespan_wrapper)
    
    @test_app.get("/")
    async def root():
        return {"message": "Test"}
    
    # Test startup
    async with test_lifespan_wrapper(test_app):
        assert startup_complete is True
    
    # Test shutdown
    assert startup_complete is False

# Test configuration loading
def test_config_loading():
    """Test that configuration loads correctly"""
    with patch.dict('os.environ', {
        'ENV': 'test',
        'DEBUG': 'True',
        'PROJECT_NAME': 'TestConfig'
    }):
        from app.core.config import settings
        assert settings.ENV == 'test'
        assert settings.DEBUG is True
        assert settings.PROJECT_NAME == 'TestConfig'
