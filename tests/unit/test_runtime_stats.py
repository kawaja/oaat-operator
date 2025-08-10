"""Unit tests for runtime statistics collection and prediction."""

import pytest
import math

from oaatoperator.runtime_stats import JobRuntimeStats, RuntimeStatsManager


class TestJobRuntimeStats:
    """Test the JobRuntimeStats class."""

    def test_init_defaults(self):
        """Test default initialization."""
        stats = JobRuntimeStats()
        assert stats.sample_size == 100
        assert stats.sample == []
        assert stats.count == 0
        assert stats.total_runtime_seconds == 0.0
        assert stats.sum_of_squares == 0.0
        assert stats.min_runtime == float('inf')
        assert stats.max_runtime == 0.0
        assert stats.last_updated is None

    def test_init_custom_sample_size(self):
        """Test initialization with custom sample size."""
        stats = JobRuntimeStats(sample_size=50)
        assert stats.sample_size == 50
        assert len(stats.sample) == 0

    def test_add_runtime_single_value(self):
        """Test adding a single runtime value."""
        stats = JobRuntimeStats()
        stats.add_runtime(120.5)

        assert stats.count == 1
        assert stats.total_runtime_seconds == 120.5
        assert stats.sum_of_squares == 120.5 * 120.5
        assert stats.min_runtime == 120.5
        assert stats.max_runtime == 120.5
        assert len(stats.sample) == 1
        assert stats.sample[0] == 120.5
        assert stats.last_updated is not None

    def test_add_runtime_multiple_values(self):
        """Test adding multiple runtime values."""
        stats = JobRuntimeStats()
        runtimes = [100, 150, 120, 180, 90]

        for runtime in runtimes:
            stats.add_runtime(runtime)

        assert stats.count == 5
        assert stats.total_runtime_seconds == sum(runtimes)
        assert stats.sum_of_squares == sum(r * r for r in runtimes)
        assert stats.min_runtime == 90
        assert stats.max_runtime == 180
        assert len(stats.sample) == 5
        assert stats.sample == sorted(runtimes)  # Sample should be sorted

    def test_add_runtime_invalid_value(self):
        """Test adding invalid runtime values."""
        stats = JobRuntimeStats()

        with pytest.raises(ValueError):
            stats.add_runtime(0)

        with pytest.raises(ValueError):
            stats.add_runtime(-10)

    def test_reservoir_sampling(self):
        """Test that reservoir sampling maintains bounded sample size."""
        stats = JobRuntimeStats(sample_size=10)

        # Add more runtimes than sample size
        for i in range(50):
            stats.add_runtime(float(i + 100))  # Values from 100 to 149

        assert stats.count == 50
        assert len(stats.sample) == 10  # Sample size should be bounded
        assert all(100 <= val <= 149 for val in stats.sample)  # All values in range
        assert stats.sample == sorted(stats.sample)  # Sample should be sorted

    def test_get_percentile_empty(self):
        """Test percentile calculation with no data."""
        stats = JobRuntimeStats()
        assert stats.get_percentile(0.5) is None
        assert stats.get_percentile(0.9) is None

    def test_get_percentile_single_value(self):
        """Test percentile calculation with single value."""
        stats = JobRuntimeStats()
        stats.add_runtime(100)

        assert stats.get_percentile(0.0) == 100
        assert stats.get_percentile(0.5) == 100
        assert stats.get_percentile(0.9) == 100
        assert stats.get_percentile(1.0) == 100

    def test_get_percentile_multiple_values(self):
        """Test percentile calculation with multiple values."""
        stats = JobRuntimeStats()
        runtimes = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]  # 10 values

        for runtime in runtimes:
            stats.add_runtime(runtime)

        # Test various percentiles
        # Note: With 10 values (indices 0-9), percentile calculation uses int(percentile * len)
        # 0.0 * 10 = 0 -> index 0 -> value 10
        # 0.5 * 10 = 5 -> index 5 -> value 60 (not 50, as 50 is at index 4)
        # 0.9 * 10 = 9 -> index 9 -> value 100
        assert stats.get_percentile(0.0) == 10   # 0th percentile
        assert stats.get_percentile(0.5) == 60   # 50th percentile (median)
        assert stats.get_percentile(0.9) == 100  # 90th percentile
        assert stats.get_percentile(1.0) == 100  # 100th percentile handled properly

    def test_get_percentile_invalid_range(self):
        """Test percentile calculation with invalid percentile values."""
        stats = JobRuntimeStats()
        stats.add_runtime(100)

        assert stats.get_percentile(-0.1) is None
        assert stats.get_percentile(1.1) is None

    def test_get_mean_empty(self):
        """Test mean calculation with no data."""
        stats = JobRuntimeStats()
        assert stats.get_mean() is None

    def test_get_mean_single_value(self):
        """Test mean calculation with single value."""
        stats = JobRuntimeStats()
        stats.add_runtime(150)
        assert stats.get_mean() == 150

    def test_get_mean_multiple_values(self):
        """Test mean calculation with multiple values."""
        stats = JobRuntimeStats()
        runtimes = [100, 200, 300]

        for runtime in runtimes:
            stats.add_runtime(runtime)

        assert stats.get_mean() == 200  # (100 + 200 + 300) / 3

    def test_get_std_deviation_insufficient_data(self):
        """Test standard deviation with insufficient data."""
        stats = JobRuntimeStats()
        assert stats.get_std_deviation() is None

        stats.add_runtime(100)
        assert stats.get_std_deviation() is None  # Need at least 2 values

    def test_get_std_deviation_multiple_values(self):
        """Test standard deviation calculation."""
        stats = JobRuntimeStats()
        runtimes = [10, 20, 30]  # Mean = 20

        for runtime in runtimes:
            stats.add_runtime(runtime)

        # Expected: sqrt(((10-20)^2 + (20-20)^2 + (30-20)^2) / 3) = sqrt(200/3) ≈ 8.16
        expected_std = math.sqrt(((10-20)**2 + (20-20)**2 + (30-20)**2) / 3)
        actual_std = stats.get_std_deviation()

        assert actual_std is not None
        assert abs(actual_std - expected_std) < 0.01

    def test_predict_runtime_no_data(self):
        """Test runtime prediction with no data."""
        stats = JobRuntimeStats()
        assert stats.predict_runtime() is None

    def test_predict_runtime_single_value(self):
        """Test runtime prediction with single value."""
        stats = JobRuntimeStats()
        stats.add_runtime(100)

        # With only one value, no std deviation, so should return the mean
        prediction = stats.predict_runtime(confidence_factor=1.5)
        assert prediction == 100

    def test_predict_runtime_multiple_values(self):
        """Test runtime prediction with multiple values."""
        stats = JobRuntimeStats()
        runtimes = [80, 90, 100, 110, 120, 150]  # P90 should be 150, mean=108.33

        for runtime in runtimes:
            stats.add_runtime(runtime)

        prediction = stats.predict_runtime(confidence_factor=1.5)
        p90 = stats.get_percentile(0.9)
        mean = stats.get_mean()
        std_dev = stats.get_std_deviation()
        conservative_estimate = mean + 1.5 * std_dev

        # Should return the higher of p90 or conservative estimate
        expected = max(p90, conservative_estimate)
        assert abs(prediction - expected) < 0.01

    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = JobRuntimeStats()
        runtimes = [100, 200, 150]

        for runtime in runtimes:
            stats.add_runtime(runtime)

        data = stats.to_dict()

        assert data['count'] == 3
        assert data['total_runtime_seconds'] == 450
        assert data['sum_of_squares'] == 100*100 + 200*200 + 150*150
        assert data['min_runtime'] == 100
        assert data['max_runtime'] == 200
        assert data['sample'] == [100, 150, 200]  # Sorted
        assert 'last_updated' in data

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'count': 3,
            'total_runtime_seconds': 450.0,
            'sum_of_squares': 65000.0,
            'min_runtime': 100.0,
            'max_runtime': 200.0,
            'sample': [100, 150, 200],
            'last_updated': '2024-08-04T19:15:00+00:00'
        }

        stats = JobRuntimeStats.from_dict(data)

        assert stats.count == 3
        assert stats.total_runtime_seconds == 450.0
        assert stats.sum_of_squares == 65000.0
        assert stats.min_runtime == 100.0
        assert stats.max_runtime == 200.0
        assert stats.sample == [100, 150, 200]
        assert stats.last_updated is not None

    def test_from_dict_empty(self):
        """Test creation from empty dictionary."""
        stats = JobRuntimeStats.from_dict({})

        assert stats.count == 0
        assert stats.total_runtime_seconds == 0.0
        assert stats.sample == []
        assert stats.last_updated is None

    def test_from_dict_oversized_sample(self):
        """Test creation from dictionary with oversized sample."""
        large_sample = list(range(150))  # 150 items
        data = {
            'count': 150,
            'total_runtime_seconds': sum(large_sample),
            'sample': large_sample
        }

        stats = JobRuntimeStats.from_dict(data, sample_size=100)

        assert len(stats.sample) == 100  # Should be trimmed
        assert stats.sample == large_sample[-100:]  # Should keep last 100

    def test_str_representation(self):
        """Test string representation."""
        stats = JobRuntimeStats()
        assert "no data" in str(stats)

        runtimes = [100, 150, 200]
        for runtime in runtimes:
            stats.add_runtime(runtime)

        str_repr = str(stats)
        assert "count=3" in str_repr
        assert "mean=150.0s" in str_repr
        assert "p50=150.0s" in str_repr


class TestRuntimeStatsManager:
    """Test the RuntimeStatsManager class."""

    def test_init(self):
        """Test initialization."""
        manager = RuntimeStatsManager(sample_size=50)
        assert manager.sample_size == 50
        assert len(manager._stats) == 0

    def test_add_runtime_new_job(self):
        """Test adding runtime for a new job."""
        manager = RuntimeStatsManager()
        manager.add_runtime('job1', 120.0)

        assert 'job1' in manager._stats
        stats = manager.get_stats('job1')
        assert stats is not None
        assert stats.count == 1

    def test_add_runtime_existing_job(self):
        """Test adding runtime for existing job."""
        manager = RuntimeStatsManager()
        manager.add_runtime('job1', 120.0)
        manager.add_runtime('job1', 130.0)

        stats = manager.get_stats('job1')
        assert stats is not None
        assert stats.count == 2

    def test_get_stats_nonexistent(self):
        """Test getting stats for non-existent job."""
        manager = RuntimeStatsManager()
        assert manager.get_stats('nonexistent') is None

    def test_predict_runtime_nonexistent(self):
        """Test predicting runtime for non-existent job."""
        manager = RuntimeStatsManager()
        assert manager.predict_runtime('nonexistent') is None

    def test_predict_runtime_existing(self):
        """Test predicting runtime for existing job."""
        manager = RuntimeStatsManager()
        manager.add_runtime('job1', 100.0)
        manager.add_runtime('job1', 200.0)

        prediction = manager.predict_runtime('job1', confidence_factor=2.0)
        assert prediction is not None
        assert prediction > 0

    def test_to_dict_empty(self):
        """Test converting empty manager to dictionary."""
        manager = RuntimeStatsManager()
        data = manager.to_dict()
        assert data == {}

    def test_to_dict_with_data(self):
        """Test converting manager with data to dictionary."""
        manager = RuntimeStatsManager()
        manager.add_runtime('job1', 100.0)
        manager.add_runtime('job2', 200.0)

        data = manager.to_dict()
        assert 'job1' in data
        assert 'job2' in data
        assert data['job1']['count'] == 1
        assert data['job2']['count'] == 1

    def test_from_dict(self):
        """Test loading manager from dictionary."""
        data = {
            'job1': {
                'count': 2,
                'total_runtime_seconds': 300.0,
                'sum_of_squares': 50000.0,
                'min_runtime': 100.0,
                'max_runtime': 200.0,
                'sample': [100, 200],
                'last_updated': '2024-08-04T19:15:00+00:00'
            },
            'job2': {
                'count': 1,
                'total_runtime_seconds': 150.0,
                'sample': [150],
            }
        }

        manager = RuntimeStatsManager()
        manager.from_dict(data)

        assert len(manager._stats) == 2

        job1_stats = manager.get_stats('job1')
        assert job1_stats is not None
        assert job1_stats.count == 2

        job2_stats = manager.get_stats('job2')
        assert job2_stats is not None
        assert job2_stats.count == 1

    def test_get_all_job_names(self):
        """Test getting all job names."""
        manager = RuntimeStatsManager()
        assert manager.get_all_job_names() == []

        manager.add_runtime('job1', 100.0)
        manager.add_runtime('job2', 200.0)

        job_names = manager.get_all_job_names()
        assert set(job_names) == {'job1', 'job2'}


class TestIntegration:
    """Integration tests for the runtime statistics system."""

    def test_realistic_workflow(self):
        """Test a realistic workflow with multiple job completions."""
        manager = RuntimeStatsManager()

        # Simulate job completions over time
        job_runtimes = {
            'backup': [120, 115, 130, 125, 140, 110, 135],
            'cleanup': [45, 50, 43, 52, 48],
            'sync': [300, 285, 310, 295, 320, 290]
        }

        # Add all runtimes
        for job_name, runtimes in job_runtimes.items():
            for runtime in runtimes:
                manager.add_runtime(job_name, runtime)

        # Test predictions
        backup_prediction = manager.predict_runtime('backup')
        cleanup_prediction = manager.predict_runtime('cleanup')
        sync_prediction = manager.predict_runtime('sync')

        assert backup_prediction is not None
        assert cleanup_prediction is not None
        assert sync_prediction is not None

        # Backup should predict around 125-140 seconds (conservative)
        assert 125 <= backup_prediction <= 150

        # Cleanup should predict around 48-55 seconds
        assert 48 <= cleanup_prediction <= 60

        # Sync should predict around 300-330 seconds
        assert 300 <= sync_prediction <= 350

    def test_round_trip_serialization(self):
        """Test that statistics survive round-trip serialization."""
        original_manager = RuntimeStatsManager()

        # Add some data
        runtimes = [100, 120, 110, 130, 105, 125, 115]
        for runtime in runtimes:
            original_manager.add_runtime('test_job', runtime)

        # Serialize and deserialize
        data = original_manager.to_dict()
        new_manager = RuntimeStatsManager()
        new_manager.from_dict(data)

        # Verify data is preserved
        original_stats = original_manager.get_stats('test_job')
        new_stats = new_manager.get_stats('test_job')

        assert original_stats is not None
        assert new_stats is not None
        assert new_stats.count == original_stats.count
        assert new_stats.get_mean() == original_stats.get_mean()
        assert new_stats.sample == original_stats.sample

        # Predictions should be the same
        original_prediction = original_manager.predict_runtime('test_job')
        new_prediction = new_manager.predict_runtime('test_job')
        assert abs(original_prediction - new_prediction) < 0.01

    def test_per_item_statistics_storage_format(self):
        """Test that the per-item statistics storage format works correctly."""
        import json

        # Test data flattening and reconstruction
        original_manager = RuntimeStatsManager()

        # Add some test data
        runtimes = [90, 95, 100, 105, 110]
        for runtime in runtimes:
            original_manager.add_runtime('test-item', runtime)

        # Get the statistics for flattening
        stats = original_manager.get_stats('test-item')
        assert stats is not None

        stats_dict = stats.to_dict()

        # Simulate the flattening process that would happen in _save_item_runtime_stats
        flattened_data = {
            'runtime_count': str(stats_dict.get('count', 0)),
            'runtime_total': str(stats_dict.get('total_runtime_seconds', 0.0)),
            'runtime_sum_squares': str(stats_dict.get('sum_of_squares', 0.0)),
            'runtime_min': str(stats_dict.get('min_runtime', 0.0)),
            'runtime_max': str(stats_dict.get('max_runtime', 0.0)),
            'runtime_sample': json.dumps(stats_dict.get('sample', [])),
            'runtime_last_updated': stats_dict.get('last_updated', '')
        }

        # Simulate the reconstruction process that would happen in _load_item_runtime_stats
        reconstructed_dict = {
            'count': int(flattened_data.get('runtime_count', 0)),
            'total_runtime_seconds': float(flattened_data.get('runtime_total', 0.0)),
            'sum_of_squares': float(flattened_data.get('runtime_sum_squares', 0.0)),
            'min_runtime': float(flattened_data.get('runtime_min', float('inf'))),
            'max_runtime': float(flattened_data.get('runtime_max', 0.0)),
            'sample': json.loads(flattened_data.get('runtime_sample', '[]')),
            'last_updated': flattened_data.get('runtime_last_updated')
        }

        # Verify round-trip fidelity
        reconstructed_stats = JobRuntimeStats.from_dict(reconstructed_dict)

        assert reconstructed_stats.count == 5
        assert reconstructed_stats.get_mean() == 100.0  # (90+95+100+105+110)/5
        assert reconstructed_stats.sample == [90, 95, 100, 105, 110]
        assert reconstructed_stats.min_runtime == 90.0
        assert reconstructed_stats.max_runtime == 110.0

        # Test prediction functionality
        prediction = reconstructed_stats.predict_runtime()
        assert prediction is not None
        assert prediction >= 100.0  # Should be at least the mean

