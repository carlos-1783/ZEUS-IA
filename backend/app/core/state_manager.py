import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self, state_file: str = 'system_state.json'):
        """
        Manages the persistence of system state to a JSON file.
        
        Args:
            state_file: Name of the file to store the state in (will be created in the app directory)
        """
        # Get the directory of the current file
        current_dir = Path(__file__).parent.parent
        self.state_file = current_dir / 'data' / state_file
        
        # Ensure the data directory exists
        self.state_file.parent.mkdir(exist_ok=True)
        
        # Initialize with default state
        self._state = {
            'empresa_actual': '',
            'empresa_activada': False,
            'modulos_activos': {
                'ventas': False,
                'inventario': False,
                'facturacion': False,
                'marketing': False
            },
            'ultima_activacion': None,
            'version': '1.0.0'
        }
        
        # Load existing state if the file exists
        self._load_state()
    
    def _load_state(self) -> None:
        """Load state from the state file if it exists."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    loaded_state = json.load(f)
                    # Only update existing keys to preserve structure
                    for key in self._state:
                        if key in loaded_state:
                            self._state[key] = loaded_state[key]
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Could not load state from %s: %s", self.state_file, e)
    
    def _save_state(self) -> None:
        """Save the current state to the state file."""
        try:
            # Create a temporary file first to ensure atomic write
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
            
            # On Windows, we need to remove the destination file first
            if os.name == 'nt' and self.state_file.exists():
                os.remove(self.state_file)
            
            # Rename the temp file to the actual state file
            os.rename(temp_file, self.state_file)
        except (IOError, OSError) as e:
            logger.error("Error saving state to %s: %s", self.state_file, e)
    
    def get_state(self) -> Dict[str, Any]:
        """Get a copy of the current state."""
        return self._state.copy()
    
    def update_state(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update the state with the given values and persist it.
        
        Args:
            updates: Dictionary of updates to apply to the state
            
        Returns:
            The updated state
        """
        import datetime
        
        # Special handling for activation
        if 'empresa_activada' in updates and updates['empresa_activada']:
            updates['ultima_activacion'] = datetime.datetime.utcnow().isoformat()
        
        # Update the state
        for key, value in updates.items():
            if key in self._state:
                if isinstance(self._state[key], dict) and isinstance(value, dict):
                    self._state[key].update(value)
                else:
                    self._state[key] = value
        
        # Save the updated state
        self._save_state()
        return self.get_state()
    
    def reset_state(self) -> Dict[str, Any]:
        """Reset the state to defaults and return the new state."""
        self._state = {
            'empresa_actual': '',
            'empresa_activada': False,
            'modulos_activos': {
                'ventas': False,
                'inventario': False,
                'facturacion': False,
                'marketing': False
            },
            'ultima_activacion': None,
            'version': '1.0.0'
        }
        self._save_state()
        return self.get_state()

# Create a singleton instance
state_manager = StateManager()
