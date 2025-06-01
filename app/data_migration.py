import os
import json
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

try:
    from .database import get_db_manager
    from .models import Hypothesis, ResearchGoal
except ImportError:
    # Handle case when imported directly
    from database import get_db_manager
    from models import Hypothesis, ResearchGoal

logger = logging.getLogger(__name__)

class DataMigrator:
    """Migrates data from results folder log files to the database"""
    
    def __init__(self, results_folder: str = "results"):
        self.results_folder = Path(results_folder)
        self.db_manager = get_db_manager()
    
    def migrate_all_logs(self) -> Dict[str, int]:
        """Migrate all log files from results folder to database"""
        if not self.results_folder.exists():
            logger.warning(f"Results folder {self.results_folder} does not exist")
            return {"sessions_created": 0, "logs_migrated": 0}
        
        log_files = list(self.results_folder.glob("app_log_*.txt"))
        logger.info(f"Found {len(log_files)} log files to migrate")
        
        sessions_created = 0
        logs_migrated = 0
        
        for log_file in log_files:
            try:
                session_data = self._parse_log_file(log_file)
                if session_data:
                    self._create_session_from_log(session_data)
                    sessions_created += 1
                    logs_migrated += len(session_data.get('log_entries', []))
                    logger.info(f"Migrated session from {log_file.name}")
            except Exception as e:
                logger.error(f"Failed to migrate {log_file.name}: {e}")
        
        return {"sessions_created": sessions_created, "logs_migrated": logs_migrated}
    
    def _parse_log_file(self, log_file: Path) -> Optional[Dict]:
        """Parse a single log file and extract session data"""
        session_data = {
            'session_id': None,
            'research_goal': None,
            'hypotheses': [],
            'tournament_results': [],
            'meta_reviews': [],
            'log_entries': [],
            'created_at': None
        }
        
        # Extract timestamp from filename
        filename_match = re.search(r'app_log_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.txt', log_file.name)
        if filename_match:
            timestamp_str = filename_match.group(1)
            session_data['created_at'] = datetime.strptime(timestamp_str, '%Y-%m-%d_%H-%M-%S').isoformat()
            session_data['session_id'] = f"migrated_{timestamp_str}"
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            lines = content.split('\n')
            current_cycle = 0
            
            for line in lines:
                if not line.strip():
                    continue
                
                # Parse log entry
                log_entry = self._parse_log_line(line)
                if log_entry:
                    session_data['log_entries'].append(log_entry)
                
                # Extract research goal
                if 'Received new research goal description:' in line:
                    goal_match = re.search(r'description: (.+)$', line)
                    if goal_match:
                        session_data['research_goal'] = goal_match.group(1).strip()
                
                # Extract hypotheses
                if 'Generated hypothesis:' in line:
                    hypothesis = self._extract_hypothesis_from_log(line)
                    if hypothesis:
                        session_data['hypotheses'].append(hypothesis)
                
                # Extract cycle information
                if '--- Starting Cycle' in line:
                    cycle_match = re.search(r'Cycle (\d+)', line)
                    if cycle_match:
                        current_cycle = int(cycle_match.group(1))
                
                # Extract tournament results
                if 'Updated Elo:' in line:
                    tournament_result = self._extract_tournament_result(line, current_cycle)
                    if tournament_result:
                        session_data['tournament_results'].append(tournament_result)
                
                # Extract meta-review
                if 'Meta-review complete:' in line:
                    meta_review = self._extract_meta_review(line, current_cycle)
                    if meta_review:
                        session_data['meta_reviews'].append(meta_review)
            
            # Only return session data if we found a research goal
            if session_data['research_goal']:
                return session_data
                
        except Exception as e:
            logger.error(f"Error parsing log file {log_file}: {e}")
        
        return None
    
    def _parse_log_line(self, line: str) -> Optional[Dict]:
        """Parse a single log line"""
        # Standard log format: timestamp level logger: message
        log_pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (\w+) ([^:]+): (.+)$'
        match = re.match(log_pattern, line)
        
        if match:
            timestamp, level, module, message = match.groups()
            return {
                'timestamp': timestamp.replace(',', '.'),  # Convert to standard format
                'level': level,
                'module': module.strip(),
                'message': message.strip()
            }
        
        return None
    
    def _extract_hypothesis_from_log(self, line: str) -> Optional[Dict]:
        """Extract hypothesis data from a log line"""
        try:
            # Look for the JSON part after "Generated hypothesis:"
            json_start = line.find('{')
            if json_start != -1:
                json_str = line[json_start:]
                hypothesis_data = json.loads(json_str)
                return hypothesis_data
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _extract_tournament_result(self, line: str, iteration: int) -> Optional[Dict]:
        """Extract tournament result from Elo update log line"""
        # Pattern: "Updated Elo: Winner G1234 -> 1250.0, Loser G5678 -> 1150.0"
        pattern = r'Winner (\w+) -> ([\d.]+), Loser (\w+) -> ([\d.]+)'
        match = re.search(pattern, line)
        
        if match:
            winner_id, winner_score, loser_id, loser_score = match.groups()
            return {
                'iteration': iteration,
                'winner_id': winner_id,
                'loser_id': loser_id,
                'winner_score_after': float(winner_score),
                'loser_score_after': float(loser_score)
            }
        
        return None
    
    def _extract_meta_review(self, line: str, iteration: int) -> Optional[Dict]:
        """Extract meta-review from log line"""
        try:
            # Look for JSON after "Meta-review complete:"
            json_start = line.find('{')
            if json_start != -1:
                json_str = line[json_start:]
                meta_review_data = json.loads(json_str)
                meta_review_data['iteration'] = iteration
                return meta_review_data
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _create_session_from_log(self, session_data: Dict):
        """Create a database session from parsed log data"""
        if not session_data['research_goal']:
            logger.warning("No research goal found, skipping session creation")
            return
        
        # Create research goal object
        research_goal = ResearchGoal(
            description=session_data['research_goal'],
            constraints={},
            llm_model="unknown",  # Default since we can't extract this from logs
            num_hypotheses=len(session_data['hypotheses']),
            generation_temperature=0.7,
            reflection_temperature=0.5,
            elo_k_factor=32,
            top_k_hypotheses=2
        )
        
        # Create session in database
        session_id = session_data['session_id']
        
        # Insert session manually with custom ID
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if session already exists
            cursor.execute('SELECT id FROM research_sessions WHERE session_id = ?', (session_id,))
            if cursor.fetchone():
                logger.info(f"Session {session_id} already exists, skipping")
                return
            
            # Insert session
            timestamp = session_data['created_at'] or datetime.now().isoformat()
            settings = {
                'llm_model': research_goal.llm_model,
                'num_hypotheses': research_goal.num_hypotheses,
                'generation_temperature': research_goal.generation_temperature,
                'reflection_temperature': research_goal.reflection_temperature,
                'elo_k_factor': research_goal.elo_k_factor,
                'top_k_hypotheses': research_goal.top_k_hypotheses
            }
            
            cursor.execute('''
                INSERT INTO research_sessions 
                (session_id, research_goal, constraints, settings, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                research_goal.description,
                json.dumps(research_goal.constraints),
                json.dumps(settings),
                timestamp,
                timestamp
            ))
            
            conn.commit()
        
        # Add hypotheses
        for hyp_data in session_data['hypotheses']:
            try:
                hypothesis = Hypothesis(
                    hypothesis_id=hyp_data['id'],
                    title=hyp_data['title'],
                    text=hyp_data['text']
                )
                hypothesis.novelty_review = hyp_data.get('novelty_review')
                hypothesis.feasibility_review = hyp_data.get('feasibility_review')
                hypothesis.elo_score = hyp_data.get('elo_score', 1200.0)
                hypothesis.review_comments = hyp_data.get('review_comments', [])
                hypothesis.references = hyp_data.get('references', [])
                hypothesis.parent_ids = hyp_data.get('parent_ids', [])
                hypothesis.is_active = hyp_data.get('is_active', True)
                
                self.db_manager.save_hypothesis(hypothesis, session_id)
            except Exception as e:
                logger.warning(f"Failed to save hypothesis {hyp_data.get('id', 'unknown')}: {e}")
        
        # Add tournament results
        for result in session_data['tournament_results']:
            try:
                self.db_manager.save_tournament_result(
                    session_id=session_id,
                    iteration=result['iteration'],
                    hypothesis1_id=result['winner_id'],
                    hypothesis2_id=result['loser_id'],
                    winner_id=result['winner_id'],
                    old_elo1=1200.0,  # We don't have old scores in logs
                    old_elo2=1200.0,
                    new_elo1=result['winner_score_after'],
                    new_elo2=result['loser_score_after']
                )
            except Exception as e:
                logger.warning(f"Failed to save tournament result: {e}")
        
        # Add meta-reviews
        for review in session_data['meta_reviews']:
            try:
                critique = "; ".join(review.get('meta_review_critique', []))
                next_steps = review.get('research_overview', {}).get('suggested_next_steps', [])
                
                self.db_manager.save_meta_review(
                    session_id=session_id,
                    iteration=review['iteration'],
                    critique=critique,
                    suggested_next_steps=next_steps
                )
            except Exception as e:
                logger.warning(f"Failed to save meta-review: {e}")
        
        # Add log entries
        for log_entry in session_data['log_entries']:
            try:
                self.db_manager.log_message(
                    message=log_entry['message'],
                    level=log_entry['level'],
                    session_id=session_id,
                    module=log_entry['module'],
                    metadata=None
                )
            except Exception as e:
                logger.warning(f"Failed to save log entry: {e}")
        
        logger.info(f"Successfully migrated session {session_id}")

def migrate_results_folder(results_folder: str = "results") -> Dict[str, int]:
    """Convenience function to migrate all data from results folder"""
    migrator = DataMigrator(results_folder)
    return migrator.migrate_all_logs()