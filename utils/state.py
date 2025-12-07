"""
Pipeline State Manager
Tracks run history and enables incremental updates
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys

# Add parent to path for config
sys.path.insert(0, str(__file__).rsplit('\\', 2)[0])
from config import STATE_FILE, DATA_DIR


class PipelineState:
    """Manages pipeline state for incremental updates"""

    def __init__(self):
        self.state_file = STATE_FILE
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load state from file or create default"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass

        # Default state
        return {
            'last_run': None,
            'runs': [],
            'total_patents': 0,
            'sources': {},
        }

    def _save_state(self):
        """Save state to file"""
        # Ensure directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def record_run(self, stats: Dict):
        """
        Record a pipeline run

        Args:
            stats: Dictionary with run statistics
        """
        run_info = {
            'timestamp': datetime.now().isoformat(),
            'patents_searched': stats.get('searched', 0),
            'patents_extracted': stats.get('extracted', 0),
            'new_patents_added': stats.get('new_added', 0),
            'duplicates_removed': stats.get('duplicates_removed', 0),
            'total_after': stats.get('total_after', 0),
            'source': stats.get('source', 'unknown'),
        }

        self.state['last_run'] = run_info['timestamp']
        self.state['runs'].append(run_info)
        self.state['total_patents'] = run_info['total_after']

        # Update source counts
        source = run_info['source']
        if source not in self.state['sources']:
            self.state['sources'][source] = 0
        self.state['sources'][source] += run_info['new_patents_added']

        # Keep only last 100 runs
        if len(self.state['runs']) > 100:
            self.state['runs'] = self.state['runs'][-100:]

        self._save_state()

    def get_last_run(self) -> Optional[Dict]:
        """Get information about the last run"""
        if self.state['runs']:
            return self.state['runs'][-1]
        return None

    def get_run_history(self, limit: int = 10) -> List[Dict]:
        """Get recent run history"""
        return self.state['runs'][-limit:][::-1]

    def get_summary(self) -> Dict:
        """Get overall pipeline summary"""
        return {
            'last_run': self.state['last_run'],
            'total_runs': len(self.state['runs']),
            'total_patents': self.state['total_patents'],
            'sources': self.state['sources'],
        }

    def clear_history(self):
        """Clear run history (keep current totals)"""
        self.state['runs'] = []
        self._save_state()
