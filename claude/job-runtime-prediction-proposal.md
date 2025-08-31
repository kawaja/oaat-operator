# Job Runtime Prediction and Blackout Period Implementation

## Overview

This proposal outlines implementing runtime prediction for OAAT jobs to support blackout periods - time windows where jobs should not be scheduled if they might run into the blackout period.

## Problem Statement

Currently, the OAAT operator schedules jobs based on frequency and failure cooloff periods, but has no awareness of:
- How long jobs typically take to complete
- Blackout periods where jobs should not be running
- The risk of a job starting before a blackout but finishing during the blackout

## Proposed Solution

### 1. Runtime Statistics Collection

Collect progressive statistics for each job type without storing individual job run details:

**Core Statistics per Job Type:**
- `count`: Total number of completed runs
- `total_runtime_seconds`: Sum of all runtimes (for mean calculation)
- `sum_of_squares`: Sum of squared runtimes (for variance/standard deviation)
- `min_runtime`: Fastest completion time observed
- `max_runtime`: Slowest completion time observed
- `sample`: Sorted array of recent runtimes (reservoir sampling, ~100 samples)
- `last_updated`: Timestamp of most recent statistics update

**Derived Metrics (calculated on-demand):**
- `mean_runtime`: `total_runtime_seconds / count`
- `std_deviation`: `sqrt((sum_of_squares / count) - (mean * mean))`
- `p90_runtime`: 90th percentile from sample array
- `p95_runtime`: 95th percentile from sample array

### 2. Progressive Statistics Algorithm

Using reservoir sampling to maintain a bounded, representative sample:

```python
class JobRuntimeStats:
    def __init__(self, sample_size=100):
        self.sample_size = sample_size
        self.sample = []  # Sorted list of recent runtimes
        self.count = 0
        self.total_runtime_seconds = 0
        self.sum_of_squares = 0
        self.min_runtime = float('inf')
        self.max_runtime = 0
        self.last_updated = None

    def add_runtime(self, runtime_seconds):
        """Add a new runtime measurement and update statistics"""
        self.count += 1
        self.total_runtime_seconds += runtime_seconds
        self.sum_of_squares += runtime_seconds * runtime_seconds
        self.min_runtime = min(self.min_runtime, runtime_seconds)
        self.max_runtime = max(self.max_runtime, runtime_seconds)
        self.last_updated = datetime.utcnow()

        # Maintain sample using reservoir sampling
        if len(self.sample) < self.sample_size:
            # Still filling initial sample
            bisect.insort(self.sample, runtime_seconds)
        else:
            # Reservoir sampling: replace random element with probability
            if random.random() < self.sample_size / self.count:
                old_idx = random.randint(0, self.sample_size - 1)
                self.sample.pop(old_idx)
                bisect.insort(self.sample, runtime_seconds)

    def get_percentile(self, percentile):
        """Get any percentile from the sample (0.0 to 1.0)"""
        if not self.sample:
            return None
        idx = int(percentile * len(self.sample))
        idx = min(idx, len(self.sample) - 1)  # Handle edge case
        return self.sample[idx]

    def predict_runtime(self, confidence_factor=1.5):
        """Predict job runtime with safety margin"""
        if self.count == 0:
            return None

        # Use 90th percentile or mean + confidence_factor * std_dev
        p90 = self.get_percentile(0.9)
        mean = self.total_runtime_seconds / self.count

        if self.count > 1:
            variance = (self.sum_of_squares / self.count) - (mean * mean)
            std_dev = math.sqrt(max(0, variance))  # Avoid negative variance due to float precision
            conservative_estimate = mean + confidence_factor * std_dev
        else:
            conservative_estimate = mean

        # Use the more conservative estimate
        return max(p90 or 0, conservative_estimate)
```

### 3. Blackout Period Logic

```python
def can_schedule_before_blackout(job_type, current_time, blackout_start, safety_buffer_factor=0.1):
    """
    Determine if a job can be safely scheduled before a blackout period.

    Args:
        job_type: The job type to check
        current_time: Current timestamp
        blackout_start: When the blackout period begins
        safety_buffer_factor: Additional safety margin (10% default)

    Returns:
        bool: True if job can be safely scheduled
    """
    stats = get_job_runtime_stats(job_type)

    if not stats or stats.count == 0:
        # No historical data - allow scheduling but log warning
        logger.warning(f"No runtime data for job type {job_type}, allowing scheduling")
        return True

    predicted_runtime = stats.predict_runtime()
    predicted_end_time = current_time + timedelta(seconds=predicted_runtime)

    # Add safety buffer
    safety_buffer = max(
        predicted_runtime * safety_buffer_factor,
        300  # Minimum 5-minute buffer
    )

    safe_end_time = predicted_end_time + timedelta(seconds=safety_buffer)

    return safe_end_time <= blackout_start
```

### 4. Data Storage

Store statistics in the individual item status sections alongside existing item metadata. This maintains consistency with the current architecture where all item-specific data (failure_count, last_success, last_failure) is stored under `status.items.<item_name>`:

```yaml
apiVersion: kawaja.net/v1
kind: OaatGroup
metadata:
  name: example-group
spec:
  # ... existing spec
status:
  items:
    item1:
      # Existing item status fields
      failure_count: 0
      last_success: "2024-08-04T19:15:00Z"
      last_failure: "2024-08-03T14:30:00Z"
      # New runtime statistics fields
      runtime_count: "150"
      runtime_total: "45000.0"
      runtime_sum_squares: "15750000.0"
      runtime_min: "120.0"
      runtime_max: "600.0"
      runtime_sample: "[180, 195, 210, 240, 285, 300, 315, 420, 450, 480, 520]"
      runtime_last_updated: "2024-08-04T19:15:00Z"
    item2:
      # Existing item status fields
      failure_count: 1
      last_success: "2024-08-04T18:30:00Z"
      last_failure: "2024-08-04T10:15:00Z"
      # New runtime statistics fields
      runtime_count: "75"
      runtime_total: "22500.0"
      runtime_sum_squares: "7125000.0"
      runtime_min: "200.0"
      runtime_max: "450.0"
      runtime_sample: "[210, 220, 240, 280, 300, 320, 350, 380, 400, 420]"
      runtime_last_updated: "2024-08-04T18:30:00Z"
```

**Storage Benefits:**
- **Architectural Consistency**: All item-specific data is co-located under `status.items.<item_name>`
- **Operational Simplicity**: Easy to inspect per-item statistics alongside other item metadata
- **Infrastructure Reuse**: Leverages existing `set_item_status()` method that handles both kopf and kube object scenarios
- **Data Locality**: Related item information is grouped together for better maintainability

**Storage Implementation:**
- Statistics are flattened to simple key-value pairs that work with `set_item_status()`
- Complex data (like the sample array) is stored as JSON strings
- All values are stored as strings to match the existing pattern for item status fields
- Loading reconstructs the `JobRuntimeStats` objects from the flattened representation

### 5. Configuration

Add blackout configuration to OaatGroup spec:

```yaml
apiVersion: kawaja.net/v1
kind: OaatGroup
metadata:
  name: example-group
spec:
  items: ["item1", "item2"]
  frequency: "1h"
  # ... existing fields
  blackout_periods:
    - name: "maintenance"
      schedule: "0 14 * * 1-5"  # 2 PM weekdays (cron format)
      duration: "3h"            # 3 hours
      timezone: "America/New_York"
  runtime_prediction:
    enabled: true
    confidence_factor: 1.5      # How conservative predictions should be
    safety_buffer_factor: 0.1   # Additional 10% safety margin
    sample_size: 100            # Number of recent runtimes to keep
```

## Implementation Plan

### Phase 1: Statistics Collection ✅
1. ✅ Add `JobRuntimeStats` class with reservoir sampling algorithm
2. ✅ Add `RuntimeStatsManager` to handle multiple job types
3. ✅ Modify pod success handlers to record job completion times (via `mark_item_success`)
4. ✅ Store statistics in per-item status fields using `set_item_status()`
5. ✅ Implement loading of statistics from per-item storage on initialization
6. ✅ Add comprehensive unit tests for statistics calculations (35 test cases)

**Architecture Decision**: Statistics are stored per-item under `status.items.<item_name>.runtime_*` fields rather than in a global `status.runtime_stats` section. This maintains consistency with existing item data storage patterns and leverages the existing `set_item_status()` infrastructure that handles both kopf and kube object scenarios.

### Phase 2: Blackout Period Configuration
1. Extend OaatGroup CRD schema with blackout configuration
2. Add cron parsing for blackout schedules
3. Implement blackout period calculation logic
4. Add validation for blackout configuration

### Phase 3: Scheduling Integration
1. Modify job selection logic to check blackout constraints
2. Add runtime prediction to scheduling decisions
3. Add logging and metrics for blackout-related scheduling decisions
4. Integration tests with various blackout scenarios

### Phase 4: Observability and Tuning
1. Add metrics for prediction accuracy
2. Add alerts for jobs that exceed predicted runtimes
3. Dashboard showing runtime trends and prediction effectiveness
4. Documentation and examples

## Benefits

1. **Predictable Operations**: Jobs won't unexpectedly run during maintenance windows
2. **Minimal Storage**: Progressive statistics require only ~1KB per job type
3. **Self-Learning**: Statistics improve automatically over time
4. **Flexible**: Supports multiple blackout periods with different schedules
5. **Conservative**: Built-in safety margins prevent edge cases
6. **Backward Compatible**: Existing OaatGroups continue working unchanged

## Considerations

1. **Cold Start**: New job types have no historical data - could use configurable default estimates
2. **Changing Job Characteristics**: Sample-based approach adapts to changing job behavior over time
3. **Storage Growth**: With reservoir sampling, storage per job type is bounded regardless of execution count
4. **Time Zones**: Blackout schedules should support timezone specifications
5. **Holiday Handling**: Consider extending blackout periods to support holiday calendars

## Example Usage

```yaml
# OaatGroup with blackout periods
apiVersion: kawaja.net/v1
kind: OaatGroup
metadata:
  name: database-maintenance
spec:
  items: ["backup-db", "vacuum-tables", "update-stats"]
  frequency: "6h"
  blackout_periods:
    - name: "business-hours"
      schedule: "0 9 * * 1-5"   # 9 AM weekdays
      duration: "8h"            # Until 5 PM
      timezone: "America/New_York"
    - name: "weekend-maintenance"
      schedule: "0 2 * * 6"     # 2 AM Saturdays
      duration: "4h"            # 4-hour maintenance window
  runtime_prediction:
    enabled: true
    confidence_factor: 2.0      # Very conservative
    safety_buffer_factor: 0.15  # 15% safety margin
```

With this configuration, if a database backup typically takes 45 minutes but could take up to 90 minutes (P90), the operator would avoid scheduling it after 7:45 AM on weekdays (9 AM - 90 minutes - 15% buffer = 7:43 AM).
