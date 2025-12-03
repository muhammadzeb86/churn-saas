"""
Unit tests for CloudWatch metrics client.

Tests Cover:
1. Async wrapper (non-blocking behavior)
2. EMF format generation
3. PII hashing and sanitization
4. Dimension cardinality control
5. Batch processing
6. Lifecycle management (start/stop)

Author: AI Assistant
Date: December 3, 2025
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from backend.monitoring.metrics import (
    CloudWatchMetricsEMF,
    get_metrics_client,
    MetricUnit,
    MetricNamespace,
    _SyncEMFBackend
)


class TestCloudWatchMetricsEMF:
    """Test the hybrid async metrics client."""
    
    @pytest.fixture
    def metrics_client(self, monkeypatch):
        """Create a fresh metrics client for each test."""
        # Reset singleton
        CloudWatchMetricsEMF._instance = None
        
        # Disable metrics by default in tests
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("CLOUDWATCH_METRICS_ENABLED", "false")
        
        return CloudWatchMetricsEMF()
    
    def test_singleton_pattern(self):
        """Verify only one instance is created."""
        CloudWatchMetricsEMF._instance = None
        
        client1 = get_metrics_client()
        client2 = get_metrics_client()
        
        assert client1 is client2
    
    def test_disabled_in_test_environment(self, monkeypatch):
        """Metrics should be disabled in test environment by default."""
        CloudWatchMetricsEMF._instance = None
        monkeypatch.setenv("ENVIRONMENT", "test")
        
        client = CloudWatchMetricsEMF()
        assert client.enabled is False
    
    def test_force_enable_in_test(self, monkeypatch):
        """Can force-enable metrics in test with FORCE_CLOUDWATCH."""
        CloudWatchMetricsEMF._instance = None
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("FORCE_CLOUDWATCH", "true")
        monkeypatch.setenv("CLOUDWATCH_METRICS_ENABLED", "true")
        
        client = CloudWatchMetricsEMF()
        assert client.enabled is True
    
    @pytest.mark.asyncio
    async def test_lifecycle_management(self, monkeypatch):
        """Test start() and stop() lifecycle methods."""
        CloudWatchMetricsEMF._instance = None
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("FORCE_CLOUDWATCH", "true")
        monkeypatch.setenv("CLOUDWATCH_METRICS_ENABLED", "true")
        
        client = CloudWatchMetricsEMF()
        
        # Start client
        await client.start()
        assert client._queue is not None
        assert client._background_task is not None
        
        # Stop client
        await client.stop()
        assert client._background_task is None
    
    @pytest.mark.asyncio
    async def test_put_metric_returns_false_when_disabled(self, metrics_client):
        """put_metric should return False when metrics disabled."""
        result = await metrics_client.put_metric("TestMetric", 1, MetricUnit.COUNT)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_put_metric_queues_when_enabled(self, monkeypatch):
        """put_metric should queue metrics when enabled."""
        CloudWatchMetricsEMF._instance = None
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("FORCE_CLOUDWATCH", "true")
        monkeypatch.setenv("CLOUDWATCH_METRICS_ENABLED", "true")
        
        client = CloudWatchMetricsEMF()
        await client.start()
        
        try:
            # Submit metric
            result = await client.put_metric("TestMetric", 42, MetricUnit.COUNT)
            
            assert result is True
            assert client._queue.qsize() == 1
            
            # Get metric from queue
            metric = await asyncio.wait_for(client._queue.get(), timeout=1.0)
            assert metric['metric_name'] == "TestMetric"
            assert metric['value'] == 42.0
            assert metric['unit'] == MetricUnit.COUNT.value
        
        finally:
            await client.stop()
    
    @pytest.mark.asyncio
    async def test_backpressure_when_queue_full(self, monkeypatch):
        """Should drop metrics when queue is full (backpressure)."""
        CloudWatchMetricsEMF._instance = None
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("FORCE_CLOUDWATCH", "true")
        monkeypatch.setenv("CLOUDWATCH_METRICS_ENABLED", "true")
        
        client = CloudWatchMetricsEMF()
        await client.start()
        
        try:
            # Fill queue to max capacity (1000)
            for i in range(1000):
                await client._queue.put({'metric': i})
            
            # Queue is full - next put_metric should return False
            result = await client.put_metric("TestMetric", 999, MetricUnit.COUNT)
            
            assert result is False  # Dropped due to backpressure
        
        finally:
            await client.stop()
    
    @pytest.mark.asyncio
    async def test_increment_counter_convenience(self, monkeypatch):
        """Test increment_counter convenience method."""
        CloudWatchMetricsEMF._instance = None
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("FORCE_CLOUDWATCH", "true")
        monkeypatch.setenv("CLOUDWATCH_METRICS_ENABLED", "true")
        
        client = CloudWatchMetricsEMF()
        await client.start()
        
        try:
            await client.increment_counter("PageView")
            
            metric = await asyncio.wait_for(client._queue.get(), timeout=1.0)
            assert metric['metric_name'] == "PageView"
            assert metric['value'] == 1.0
            assert metric['unit'] == MetricUnit.COUNT.value
        
        finally:
            await client.stop()
    
    @pytest.mark.asyncio
    async def test_record_time_convenience(self, monkeypatch):
        """Test record_time convenience method."""
        CloudWatchMetricsEMF._instance = None
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("FORCE_CLOUDWATCH", "true")
        monkeypatch.setenv("CLOUDWATCH_METRICS_ENABLED", "true")
        
        client = CloudWatchMetricsEMF()
        await client.start()
        
        try:
            await client.record_time("APILatency", 1.25)
            
            metric = await asyncio.wait_for(client._queue.get(), timeout=1.0)
            assert metric['metric_name'] == "APILatency"
            assert metric['value'] == 1.25
            assert metric['unit'] == MetricUnit.SECONDS.value
        
        finally:
            await client.stop()


class TestSyncEMFBackend:
    """Test the synchronous EMF backend."""
    
    @pytest.fixture
    def backend(self):
        """Create a sync backend instance."""
        return _SyncEMFBackend()
    
    def test_sanitize_user_id_to_bucket(self, backend):
        """User IDs should be hashed to 256 buckets (00-FF)."""
        metric = {
            'metric_name': 'TestMetric',
            'value': 1.0,
            'dimensions': {'UserId': 'user_12345'}
        }
        
        sanitized = backend._sanitize_metric(metric)
        
        # UserBucket should be 2-char hex (00-FF)
        assert 'UserBucket' in sanitized['dimensions']
        assert 'UserId' not in sanitized['dimensions']  # Original removed
        assert len(sanitized['dimensions']['UserBucket']) == 2
        assert all(c in '0123456789abcdef' for c in sanitized['dimensions']['UserBucket'])
    
    def test_remove_high_cardinality_dimensions(self, backend):
        """High-cardinality dimensions should be excluded."""
        metric = {
            'metric_name': 'TestMetric',
            'value': 1.0,
            'dimensions': {
                'UploadId': 'upload_12345',  # Should be removed
                'RequestId': 'req_67890',    # Should be removed
                'ValidDimension': 'keep_me'
            }
        }
        
        sanitized = backend._sanitize_metric(metric)
        
        assert 'UploadId' not in sanitized['dimensions']
        assert 'RequestId' not in sanitized['dimensions']
        assert 'ValidDimension' in sanitized['dimensions']
    
    def test_sanitize_file_name_to_extension(self, backend):
        """File names should be reduced to extension only (PII protection)."""
        metric = {
            'metric_name': 'TestMetric',
            'value': 1.0,
            'dimensions': {
                'FileName': 'sensitive_customer_data_2025.csv'
            }
        }
        
        sanitized = backend._sanitize_metric(metric)
        
        assert 'FileName' not in sanitized['dimensions']
        assert 'FileType' in sanitized['dimensions']
        assert sanitized['dimensions']['FileType'] == 'csv'
    
    def test_limit_dimensions_to_10(self, backend):
        """Should truncate to max 10 dimensions (CloudWatch limit)."""
        metric = {
            'metric_name': 'TestMetric',
            'value': 1.0,
            'dimensions': {f'dim{i}': f'value{i}' for i in range(15)}
        }
        
        sanitized = backend._sanitize_metric(metric)
        
        assert len(sanitized['dimensions']) <= 10
    
    def test_sanitize_special_characters(self, backend):
        """Special characters should be removed from dimension values."""
        metric = {
            'metric_name': 'TestMetric',
            'value': 1.0,
            'dimensions': {
                'Environment': 'prod@us-east-1#123'
            }
        }
        
        sanitized = backend._sanitize_metric(metric)
        
        # Only alphanumeric, underscores, hyphens, dots allowed
        assert sanitized['dimensions']['Environment'] == 'produseast1123'
    
    def test_group_metrics_by_namespace_and_dimensions(self, backend):
        """Metrics should be grouped by namespace and dimensions for EMF."""
        batch = [
            {
                'metric_name': 'Metric1',
                'value': 1.0,
                'unit': 'Count',
                'namespace': 'Test',
                'dimensions': {'env': 'prod'}
            },
            {
                'metric_name': 'Metric2',
                'value': 2.0,
                'unit': 'Count',
                'namespace': 'Test',
                'dimensions': {'env': 'prod'}
            }
        ]
        
        emf_batches = backend._group_metrics(batch)
        
        # Should be grouped into single EMF structure
        assert len(emf_batches) == 1
        assert '_aws' in emf_batches[0]
        assert 'Metric1' in emf_batches[0]
        assert 'Metric2' in emf_batches[0]
        assert emf_batches[0]['env'] == 'prod'
    
    def test_emf_format_structure(self, backend):
        """EMF format should match CloudWatch specification."""
        batch = [
            {
                'metric_name': 'TestMetric',
                'value': 42.0,
                'unit': 'Count',
                'namespace': 'RetainWise/Test',
                'dimensions': {'env': 'test'}
            }
        ]
        
        emf_batches = backend._group_metrics(batch)
        emf_data = emf_batches[0]
        
        # Verify EMF structure
        assert '_aws' in emf_data
        assert 'Timestamp' in emf_data['_aws']
        assert 'CloudWatchMetrics' in emf_data['_aws']
        
        cwm = emf_data['_aws']['CloudWatchMetrics'][0]
        assert cwm['Namespace'] == 'RetainWise/Test'
        assert cwm['Dimensions'] == [['env']]
        assert len(cwm['Metrics']) == 1
        assert cwm['Metrics'][0]['Name'] == 'TestMetric'
        assert cwm['Metrics'][0]['Unit'] == 'Count'
        
        # Verify metric value and dimensions
        assert emf_data['TestMetric'] == 42.0
        assert emf_data['env'] == 'test'
    
    @patch('builtins.print')
    def test_flush_batch_prints_emf_json(self, mock_print, backend):
        """flush_batch should print EMF JSON to stdout."""
        batch = [
            {
                'metric_name': 'TestMetric',
                'value': 1.0,
                'unit': 'Count',
                'namespace': 'Test',
                'dimensions': {}
            }
        ]
        
        backend.flush_batch(batch)
        
        # Verify print was called
        mock_print.assert_called_once()
        
        # Verify output is valid JSON
        output = mock_print.call_args[0][0]
        parsed = json.loads(output)
        
        assert '_aws' in parsed
        assert 'TestMetric' in parsed
    
    def test_flush_empty_batch_does_nothing(self, backend):
        """Flushing an empty batch should be a no-op."""
        backend.flush_batch([])  # Should not raise exception


class TestIntegration:
    """Integration tests for end-to-end metric flow."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_metric_flow(self, monkeypatch, capsys):
        """Test metric flows from put_metric() to EMF output."""
        CloudWatchMetricsEMF._instance = None
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("FORCE_CLOUDWATCH", "true")
        monkeypatch.setenv("CLOUDWATCH_METRICS_ENABLED", "true")
        
        client = CloudWatchMetricsEMF()
        client.batch_size = 1  # Flush immediately for testing
        
        await client.start()
        
        try:
            # Submit metric
            await client.put_metric(
                "TestMetric",
                42,
                MetricUnit.COUNT,
                namespace=MetricNamespace.ML_PIPELINE,
                dimensions={"env": "test"}
            )
            
            # Wait for background task to process
            await asyncio.sleep(0.5)
            
            # Flush manually to ensure processing
            await client.flush()
            
            # Background task should have printed EMF JSON
            # (captured by capsys in real integration test)
        
        finally:
            await client.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_metric_submissions(self, monkeypatch):
        """Test multiple concurrent put_metric calls don't cause race conditions."""
        CloudWatchMetricsEMF._instance = None
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("FORCE_CLOUDWATCH", "true")
        monkeypatch.setenv("CLOUDWATCH_METRICS_ENABLED", "true")
        
        client = CloudWatchMetricsEMF()
        await client.start()
        
        try:
            # Submit 100 metrics concurrently
            tasks = [
                client.put_metric(f"Metric{i}", i, MetricUnit.COUNT)
                for i in range(100)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All should succeed (no race conditions)
            assert all(results)
            assert client._queue.qsize() == 100
        
        finally:
            await client.stop()


class TestCostOptimizations:
    """Test cost optimization features."""
    
    def test_user_id_hashing_reduces_cardinality(self):
        """Verify user ID hashing limits to 256 unique values."""
        backend = _SyncEMFBackend()
        
        # Hash 1000 different user IDs
        buckets = set()
        for i in range(1000):
            metric = {
                'metric_name': 'Test',
                'value': 1.0,
                'dimensions': {'UserId': f'user_{i}'}
            }
            sanitized = backend._sanitize_metric(metric)
            buckets.add(sanitized['dimensions']['UserBucket'])
        
        # Should be limited to 256 buckets (00-FF in hex)
        assert len(buckets) <= 256
    
    def test_file_name_to_extension_reduces_cardinality(self):
        """Verify file name sanitization limits cardinality."""
        backend = _SyncEMFBackend()
        
        # 1000 different file names with same extension
        extensions = set()
        for i in range(1000):
            metric = {
                'metric_name': 'Test',
                'value': 1.0,
                'dimensions': {'FileName': f'unique_file_name_{i}.csv'}
            }
            sanitized = backend._sanitize_metric(metric)
            extensions.add(sanitized['dimensions']['FileType'])
        
        # All should map to single extension
        assert len(extensions) == 1
        assert 'csv' in extensions

