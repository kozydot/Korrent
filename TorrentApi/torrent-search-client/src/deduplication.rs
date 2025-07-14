use crate::{cache::CacheKey, client::ProviderResponse};
use chrono::{DateTime, Duration, Utc};
use dashmap::DashMap;
use futures::Future;
use std::sync::Arc;
use tokio::sync::oneshot;

/// Configuration for request deduplication
#[derive(Clone, Debug)]
pub struct DeduplicationConfig {
    /// How long to keep pending requests before timing out
    pub request_timeout: Duration,
    /// Whether deduplication is enabled
    pub enabled: bool,
}

impl Default for DeduplicationConfig {
    fn default() -> Self {
        Self {
            request_timeout: Duration::seconds(30),
            enabled: true,
        }
    }
}

/// Represents a pending request
type PendingRequest = Arc<tokio::sync::Mutex<Option<oneshot::Sender<Vec<ProviderResponse>>>>>;

/// Request deduplication system
/// When multiple identical requests come in, only the first one is executed
/// and the results are shared with all waiting requests
pub struct RequestDeduplicator {
    /// Map of cache keys to pending requests
    pending_searches: DashMap<CacheKey, (DateTime<Utc>, Vec<PendingRequest>)>,
    config: DeduplicationConfig,
}

impl RequestDeduplicator {
    pub fn new(config: DeduplicationConfig) -> Self {
        Self {
            pending_searches: DashMap::new(),
            config,
        }
    }

    /// Execute a search operation with deduplication
    /// If the same search is already in progress, wait for its result
    /// Otherwise, execute the search and notify all waiting requests
    pub async fn execute_search<F, Fut>(
        &self,
        key: CacheKey,
        search_fn: F,
    ) -> Result<Vec<ProviderResponse>, DeduplicationError>
    where
        F: FnOnce() -> Fut + Send + 'static,
        Fut: Future<Output = Vec<ProviderResponse>> + Send + 'static,
    {
        if !self.config.enabled {
            return Ok(search_fn().await);
        }

        // Clean up expired requests first
        self.cleanup_expired();

        // Check if this request is already pending
        if let Some(mut entry) = self.pending_searches.get_mut(&key) {
            log::debug!("Request already pending for key: {:?}", key);
            
            // Create a channel to receive the result
            let (tx, rx) = oneshot::channel();
            let pending_request = Arc::new(tokio::sync::Mutex::new(Some(tx)));
            entry.1.push(pending_request);

            // Wait for the result with timeout
            return match tokio::time::timeout(
                self.config.request_timeout.to_std().unwrap(),
                rx,
            ).await {
                Ok(Ok(result)) => {
                    log::debug!("Received deduplicated result for key: {:?}", key);
                    Ok(result)
                }
                Ok(Err(_)) => {
                    log::warn!("Sender dropped for key: {:?}", key);
                    Err(DeduplicationError::SenderDropped)
                }
                Err(_) => {
                    log::warn!("Request timeout for key: {:?}", key);
                    Err(DeduplicationError::Timeout)
                }
            };
        }

        // This is the first request for this key, so we'll execute it
        log::debug!("Executing new request for key: {:?}", key);
        
        // Register this request as pending
        let pending_list = vec![];
        self.pending_searches.insert(key.clone(), (Utc::now(), pending_list));

        // Execute the search
        let result = search_fn().await;

        // Notify all waiting requests and clean up
        if let Some((_, waiters)) = self.pending_searches.remove(&key) {
            log::debug!("Notifying {} waiters for key: {:?}", waiters.len(), key);
            
            for waiter in waiters {
                if let Ok(mut sender_opt) = waiter.try_lock() {
                    if let Some(sender) = sender_opt.take() {
                        let _ = sender.send(result.clone());
                    }
                }
            }
        }

        Ok(result)
    }

    /// Clean up expired pending requests
    fn cleanup_expired(&self) {
        let now = Utc::now();
        let expired_keys: Vec<_> = self.pending_searches
            .iter()
            .filter(|entry| (now - entry.value().0) > self.config.request_timeout)
            .map(|entry| entry.key().clone())
            .collect();

        for key in expired_keys {
            if let Some((_, waiters)) = self.pending_searches.remove(&key) {
                log::debug!("Cleaning up expired request for key: {:?} with {} waiters", key, waiters.len());
                
                // Notify waiters that the request timed out
                for waiter in waiters {
                    if let Ok(mut sender_opt) = waiter.try_lock() {
                        if let Some(_sender) = sender_opt.take() {
                            // Sender will be dropped, causing receiver to get an error
                        }
                    }
                }
            }
        }
    }

    /// Get statistics about pending requests
    pub fn stats(&self) -> DeduplicationStats {
        let pending_count = self.pending_searches.len();
        let total_waiters = self.pending_searches
            .iter()
            .map(|entry| entry.value().1.len())
            .sum();

        DeduplicationStats {
            pending_requests: pending_count,
            total_waiters,
        }
    }

    /// Clear all pending requests
    pub fn clear(&self) {
        self.pending_searches.clear();
        log::info!("Request deduplicator cleared");
    }
}

/// Statistics for request deduplication
#[derive(Debug)]
pub struct DeduplicationStats {
    pub pending_requests: usize,
    pub total_waiters: usize,
}

/// Errors that can occur during request deduplication
#[derive(Debug, thiserror::Error)]
pub enum DeduplicationError {
    #[error("Request timed out")]
    Timeout,
    #[error("Sender was dropped")]
    SenderDropped,
}

/// Thread-safe wrapper for the deduplicator
pub type SharedRequestDeduplicator = Arc<RequestDeduplicator>;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{cache::CacheKey, Category, Order, SearchOptions, SortColumn};
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::time::Duration as StdDuration;

    #[tokio::test]
    async fn test_request_deduplication() {
        let deduplicator = RequestDeduplicator::new(DeduplicationConfig::default());
        let execution_count = Arc::new(AtomicUsize::new(0));
        
        let search_options = SearchOptions::new(
            "test".to_string(),
            Category::Video,
            SortColumn::Seeders,
            Order::Descending,
        );
        let providers = HashSet::new();
        let key = CacheKey::from_search(&search_options, &providers);

        // Execute multiple identical requests concurrently
        let mut handles = vec![];
        for _ in 0..5 {
            let deduplicator = deduplicator.clone();
            let key = key.clone();
            let execution_count = execution_count.clone();
            
            let handle = tokio::spawn(async move {
                deduplicator.execute_search(key, || async move {
                    execution_count.fetch_add(1, Ordering::SeqCst);
                    tokio::time::sleep(StdDuration::from_millis(100)).await;
                    vec![] // Empty result for test
                }).await
            });
            
            handles.push(handle);
        }

        // Wait for all requests to complete
        for handle in handles {
            handle.await.unwrap().unwrap();
        }

        // Should have executed only once due to deduplication
        assert_eq!(execution_count.load(Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn test_different_keys_not_deduplicated() {
        let deduplicator = RequestDeduplicator::new(DeduplicationConfig::default());
        let execution_count = Arc::new(AtomicUsize::new(0));
        
        let search_options1 = SearchOptions::new(
            "test1".to_string(),
            Category::Video,
            SortColumn::Seeders,
            Order::Descending,
        );
        let search_options2 = SearchOptions::new(
            "test2".to_string(),
            Category::Video,
            SortColumn::Seeders,
            Order::Descending,
        );
        
        let providers = HashSet::new();
        let key1 = CacheKey::from_search(&search_options1, &providers);
        let key2 = CacheKey::from_search(&search_options2, &providers);

        // Execute different requests concurrently
        let execution_count1 = execution_count.clone();
        let execution_count2 = execution_count.clone();
        
        let deduplicator1 = deduplicator.clone();
        let deduplicator2 = deduplicator.clone();
        
        let handle1 = tokio::spawn(async move {
            deduplicator1.execute_search(key1, || async move {
                execution_count1.fetch_add(1, Ordering::SeqCst);
                vec![]
            }).await
        });
        
        let handle2 = tokio::spawn(async move {
            deduplicator2.execute_search(key2, || async move {
                execution_count2.fetch_add(1, Ordering::SeqCst);
                vec![]
            }).await
        });

        handle1.await.unwrap().unwrap();
        handle2.await.unwrap().unwrap();

        // Should have executed twice since keys are different
        assert_eq!(execution_count.load(Ordering::SeqCst), 2);
    }
}
