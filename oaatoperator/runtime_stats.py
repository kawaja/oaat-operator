"""Runtime statistics collection and prediction for OAAT jobs.

This module implements progressive statistics collection using reservoir sampling
to track job runtimes and provide runtime predictions for scheduling decisions.
"""

import bisect
import math
import random
from datetime import datetime, timezone
from typing import Dict, Optional, Any


class JobRuntimeStats:
    """
    Tracks runtime statistics for a job type using progressive algorithms.
    
    Uses reservoir sampling to maintain a representative sample of recent runtimes
    while keeping memory usage bounded. Calculates percentiles and predictions
    without storing full runtime history.
    """
    
    def __init__(self, sample_size: int = 100):
        """Initialize runtime statistics tracker.
        
        Args:
            sample_size: Maximum number of runtime samples to keep (default: 100)
        """
        self.sample_size = sample_size
        self.sample = []  # Sorted list of recent runtimes in seconds
        self.count = 0
        self.total_runtime_seconds = 0.0
        self.sum_of_squares = 0.0
        self.min_runtime = float('inf')
        self.max_runtime = 0.0
        self.last_updated = None
    
    def add_runtime(self, runtime_seconds: float) -> None:
        """Add a new runtime measurement and update statistics.
        
        Args:
            runtime_seconds: Job runtime in seconds
        """
        if runtime_seconds <= 0:
            raise ValueError("Runtime must be positive")
            
        self.count += 1
        self.total_runtime_seconds += runtime_seconds
        self.sum_of_squares += runtime_seconds * runtime_seconds
        self.min_runtime = min(self.min_runtime, runtime_seconds)
        self.max_runtime = max(self.max_runtime, runtime_seconds)
        self.last_updated = datetime.now(timezone.utc)
        
        # Maintain sample using reservoir sampling
        if len(self.sample) < self.sample_size:
            # Still filling initial sample - insert in sorted order
            bisect.insort(self.sample, runtime_seconds)
        else:
            # Reservoir sampling: replace random element with probability sample_size/count
            if random.random() < self.sample_size / self.count:
                # Remove random element and insert new one in sorted order
                old_idx = random.randint(0, self.sample_size - 1)
                self.sample.pop(old_idx)
                bisect.insort(self.sample, runtime_seconds)
    
    def get_percentile(self, percentile: float) -> Optional[float]:
        """Get any percentile from the sample.
        
        Args:
            percentile: Percentile to calculate (0.0 to 1.0)
            
        Returns:
            Runtime at the specified percentile, or None if no data
        """
        if not self.sample or percentile < 0 or percentile > 1:
            return None
            
        idx = int(percentile * len(self.sample))
        idx = min(idx, len(self.sample) - 1)  # Handle edge case for 100th percentile
        return self.sample[idx]
    
    def get_mean(self) -> Optional[float]:
        """Get mean runtime.
        
        Returns:
            Mean runtime in seconds, or None if no data
        """
        if self.count == 0:
            return None
        return self.total_runtime_seconds / self.count
    
    def get_std_deviation(self) -> Optional[float]:
        """Get standard deviation of runtimes.
        
        Returns:
            Standard deviation in seconds, or None if insufficient data
        """
        if self.count < 2:
            return None
            
        mean = self.get_mean()
        variance = (self.sum_of_squares / self.count) - (mean * mean)
        return math.sqrt(max(0, variance))  # Avoid negative variance due to float precision
    
    def predict_runtime(self, confidence_factor: float = 1.5) -> Optional[float]:
        """Predict job runtime with safety margin.
        
        Uses the more conservative of:
        - 90th percentile from sample
        - Mean + confidence_factor * standard_deviation
        
        Args:
            confidence_factor: How many standard deviations above mean to use (default: 1.5)
            
        Returns:
            Predicted runtime in seconds, or None if no data
        """
        if self.count == 0:
            return None
            
        # Get 90th percentile from sample
        p90 = self.get_percentile(0.9)
        
        # Get conservative estimate based on mean + std_dev
        mean = self.get_mean()
        std_dev = self.get_std_deviation()
        
        if std_dev is not None:
            conservative_estimate = mean + confidence_factor * std_dev
        else:
            conservative_estimate = mean
        
        # Use the more conservative (higher) estimate
        if p90 is not None and conservative_estimate is not None:
            return max(p90, conservative_estimate)
        elif p90 is not None:
            return p90
        else:
            return conservative_estimate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary for storage.
        
        Returns:
            Dictionary representation suitable for Kubernetes status storage
        """
        return {
            'count': self.count,
            'total_runtime_seconds': self.total_runtime_seconds,
            'sum_of_squares': self.sum_of_squares,
            'min_runtime': self.min_runtime if self.min_runtime != float('inf') else 0,
            'max_runtime': self.max_runtime,
            'sample': self.sample.copy(),
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], sample_size: int = 100) -> 'JobRuntimeStats':
        """Create JobRuntimeStats from dictionary.
        
        Args:
            data: Dictionary representation from Kubernetes status
            sample_size: Maximum sample size to maintain
            
        Returns:
            JobRuntimeStats instance
        """
        stats = cls(sample_size=sample_size)
        stats.count = data.get('count', 0)
        stats.total_runtime_seconds = data.get('total_runtime_seconds', 0.0)
        stats.sum_of_squares = data.get('sum_of_squares', 0.0)
        stats.min_runtime = data.get('min_runtime', float('inf'))
        stats.max_runtime = data.get('max_runtime', 0.0)
        stats.sample = sorted(data.get('sample', []))  # Ensure sample is sorted
        
        # Trim sample to size if needed
        if len(stats.sample) > sample_size:
            stats.sample = stats.sample[-sample_size:]
            
        last_updated_str = data.get('last_updated')
        if last_updated_str:
            try:
                stats.last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                stats.last_updated = None
                
        return stats
    
    def __str__(self) -> str:
        """String representation of statistics."""
        if self.count == 0:
            return "JobRuntimeStats(no data)"
            
        mean = self.get_mean()
        p50 = self.get_percentile(0.5)
        p90 = self.get_percentile(0.9)
        predicted = self.predict_runtime()
        
        return (f"JobRuntimeStats(count={self.count}, mean={mean:.1f}s, "
                f"p50={p50:.1f}s, p90={p90:.1f}s, predicted={predicted:.1f}s)")


class RuntimeStatsManager:
    """Manages runtime statistics for multiple job types."""
    
    def __init__(self, sample_size: int = 100):
        """Initialize runtime statistics manager.
        
        Args:
            sample_size: Maximum sample size per job type
        """
        self.sample_size = sample_size
        self._stats: Dict[str, JobRuntimeStats] = {}
    
    def add_runtime(self, job_name: str, runtime_seconds: float) -> None:
        """Add runtime measurement for a job.
        
        Args:
            job_name: Name/identifier of the job
            runtime_seconds: Runtime in seconds
        """
        if job_name not in self._stats:
            self._stats[job_name] = JobRuntimeStats(self.sample_size)
        self._stats[job_name].add_runtime(runtime_seconds)
    
    def get_stats(self, job_name: str) -> Optional[JobRuntimeStats]:
        """Get statistics for a job type.
        
        Args:
            job_name: Name/identifier of the job
            
        Returns:
            JobRuntimeStats instance or None if no data
        """
        return self._stats.get(job_name)
    
    def predict_runtime(self, job_name: str, confidence_factor: float = 1.5) -> Optional[float]:
        """Predict runtime for a job type.
        
        Args:
            job_name: Name/identifier of the job
            confidence_factor: Confidence factor for prediction
            
        Returns:
            Predicted runtime in seconds or None if no data
        """
        stats = self.get_stats(job_name)
        if stats:
            return stats.predict_runtime(confidence_factor)
        return None
    
    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert all statistics to dictionary for storage.
        
        Returns:
            Dictionary mapping job names to their statistics
        """
        return {job_name: stats.to_dict() for job_name, stats in self._stats.items()}
    
    def from_dict(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Load statistics from dictionary.
        
        Args:
            data: Dictionary mapping job names to their statistics
        """
        self._stats = {}
        for job_name, stats_data in data.items():
            self._stats[job_name] = JobRuntimeStats.from_dict(stats_data, self.sample_size)
    
    def get_all_job_names(self) -> list[str]:
        """Get list of all job names with statistics.
        
        Returns:
            List of job names
        """
        return list(self._stats.keys())