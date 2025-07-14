use crate::{client::ProviderResponse, MovieOptions, SearchOptions};
use chrono::{DateTime, Duration, Utc};
use dashmap::DashMap;
use sha2::{Digest, Sha256};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::sync::Arc;

#[cfg(feature = "graphql")]
use async_graphql::SimpleObject;

/// Configuration for the cache system
#[derive(Clone, Debug)]
pub struct CacheConfig {
    /// How long to keep search results in cache
    pub search_ttl: Duration,
    /// How long to keep movie search results in cache
    pub movie_search_ttl: Duration,
    /// Maximum number of cached entries
    pub max_entries: usize,
    /// Whether caching is enabled
    pub enabled: bool,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            search_ttl: Duration::minutes(15),
            movie_search_ttl: Duration::hours(1),
            max_entries: 1000,
            enabled: true,
        }
    }
}

impl CacheConfig {
    /// Create a new cache configuration
    pub fn new(search_ttl: Duration, max_entries: usize, _cleanup_interval: Duration) -> Self {
        Self {
            search_ttl,
            movie_search_ttl: search_ttl, // Use same TTL for both for simplicity
            max_entries,
            enabled: true,
        }
    }
}

/// Cached search result with metadata
#[derive(Clone, Debug)]
pub struct CachedResult {
    pub data: Vec<ProviderResponse>,
    pub created_at: DateTime<Utc>,
    pub ttl: Duration,
}

impl CachedResult {
    pub fn new(data: Vec<ProviderResponse>, ttl: Duration) -> Self {
        Self {
            data,
            created_at: Utc::now(),
            ttl,
        }
    }

    /// Check if the cached result is still valid
    pub fn is_valid(&self) -> bool {
        Utc::now() < self.created_at + self.ttl
    }

    /// Check if the cached result will expire soon (within 10% of TTL)
    pub fn expires_soon(&self) -> bool {
        let expiry_threshold = self.ttl.num_milliseconds() / 10; // 10% of TTL
        let expires_at = self.created_at + self.ttl;
        let time_until_expiry = expires_at - Utc::now();
        time_until_expiry.num_milliseconds() < expiry_threshold
    }
}

/// Cache key for search operations
#[derive(Hash, Eq, PartialEq, Clone, Debug)]
pub enum CacheKey {
    Search(String), // Hash of search parameters
    MovieSearch(String), // Hash of movie search parameters
}

impl CacheKey {
    /// Generate a cache key for search options
    pub fn from_search(search_options: &SearchOptions, providers: &HashSet<crate::Provider>) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(search_options.query().as_bytes());
        hasher.update(format!("{:?}", search_options.category()).as_bytes());
        hasher.update(format!("{:?}", search_options.sort()).as_bytes());
        hasher.update(format!("{:?}", search_options.order()).as_bytes());
        
        // Include providers in hash to ensure different provider combinations have different keys
        let mut provider_vec: Vec<_> = providers.iter().collect();
        provider_vec.sort();
        hasher.update(format!("{:?}", provider_vec).as_bytes());
        
        let hash = hex::encode(hasher.finalize());
        CacheKey::Search(hash)
    }

    /// Generate a cache key for movie search options
    pub fn from_movie_search(movie_options: &MovieOptions, providers: &HashSet<crate::Provider>) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(movie_options.imdb().as_bytes());
        
        if let Some(title) = movie_options.title() {
            hasher.update(title.as_bytes());
        }
        hasher.update(format!("{:?}", movie_options.sort()).as_bytes());
        hasher.update(format!("{:?}", movie_options.order()).as_bytes());
        
        // Include providers in hash
        let mut provider_vec: Vec<_> = providers.iter().collect();
        provider_vec.sort();
        hasher.update(format!("{:?}", provider_vec).as_bytes());
        
        let hash = hex::encode(hasher.finalize());
        CacheKey::MovieSearch(hash)
    }
}

/// In-memory cache implementation using DashMap for thread safety
pub struct SearchCache {
    cache: DashMap<CacheKey, CachedResult>,
    pub config: CacheConfig,
}

impl SearchCache {
    pub fn new(config: CacheConfig) -> Self {
        Self {
            cache: DashMap::new(),
            config,
        }
    }

    /// Get cached result if available and valid
    pub fn get(&self, key: &CacheKey) -> Option<Vec<ProviderResponse>> {
        if !self.config.enabled {
            return None;
        }

        if let Some(cached) = self.cache.get(key) {
            if cached.is_valid() {
                log::debug!("Cache hit for key: {:?}", key);
                return Some(cached.data.clone());
            } else {
                log::debug!("Cache expired for key: {:?}", key);
                // Remove expired entry
                self.cache.remove(key);
            }
        }

        log::debug!("Cache miss for key: {:?}", key);
        None
    }

    /// Store result in cache
    pub fn put(&self, key: CacheKey, data: Vec<ProviderResponse>, ttl: Duration) {
        if !self.config.enabled {
            return;
        }

        // Check if we need to evict old entries
        if self.cache.len() >= self.config.max_entries {
            self.evict_expired();
            
            // If still at capacity, remove oldest entries
            if self.cache.len() >= self.config.max_entries {
                self.evict_oldest();
            }
        }

        let cached_result = CachedResult::new(data, ttl);
        self.cache.insert(key.clone(), cached_result);
        log::debug!("Stored in cache with key: {:?}", key);
    }

    /// Remove expired entries from cache
    pub fn evict_expired(&self) {
        let expired_keys: Vec<_> = self.cache
            .iter()
            .filter(|entry| !entry.value().is_valid())
            .map(|entry| entry.key().clone())
            .collect();

        let expired_count = expired_keys.len();
        
        for key in expired_keys {
            self.cache.remove(&key);
        }

        log::debug!("Evicted {} expired cache entries", expired_count);
    }

    /// Remove oldest entries when at capacity
    fn evict_oldest(&self) {
        let mut entries: Vec<_> = self.cache
            .iter()
            .map(|entry| (entry.key().clone(), entry.value().created_at))
            .collect();

        // Sort by creation time (oldest first)
        entries.sort_by_key(|(_, created_at)| *created_at);

        // Remove oldest 25% of entries
        let to_remove = (self.config.max_entries / 4).max(1);
        for (key, _) in entries.into_iter().take(to_remove) {
            self.cache.remove(&key);
        }

        log::debug!("Evicted {} oldest cache entries", to_remove);
    }

    /// Clear all cache entries
    pub fn clear(&self) {
        self.cache.clear();
        log::info!("Cache cleared");
    }

    /// Get cache statistics
    pub fn stats(&self) -> CacheStats {
        let total_entries = self.cache.len();
        let expired_entries = self.cache
            .iter()
            .filter(|entry| !entry.value().is_valid())
            .count();

        CacheStats {
            total_entries,
            valid_entries: total_entries - expired_entries,
            expired_entries,
            max_entries: self.config.max_entries,
        }
    }
}

/// Cache statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "graphql", derive(SimpleObject))]
pub struct CacheStats {
    pub total_entries: usize,
    pub valid_entries: usize,
    pub expired_entries: usize,
    pub max_entries: usize,
}

/// Thread-safe wrapper for the cache
pub type SharedSearchCache = Arc<SearchCache>;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Category, Order, SearchOptions, SortColumn};

    #[test]
    fn test_cache_key_generation() {
        let search_options = SearchOptions::new(
            "test movie".to_string(),
            Category::Video,
            SortColumn::Seeders,
            Order::Descending,
        );
        let providers = HashSet::new();
        
        let key1 = CacheKey::from_search(&search_options, &providers);
        let key2 = CacheKey::from_search(&search_options, &providers);
        
        assert_eq!(key1, key2);
        
        // Different query should produce different key
        let search_options2 = SearchOptions::new(
            "different movie".to_string(),
            Category::Video,
            SortColumn::Seeders,
            Order::Descending,
        );
        let key3 = CacheKey::from_search(&search_options2, &providers);
        
        assert_ne!(key1, key3);
    }

    #[test]
    fn test_cached_result_validity() {
        let data = vec![];
        let ttl = Duration::seconds(1);
        let cached = CachedResult::new(data, ttl);
        
        assert!(cached.is_valid());
        
        // Simulate expired result
        let expired_cached = CachedResult {
            data: vec![],
            created_at: Utc::now() - Duration::seconds(2),
            ttl: Duration::seconds(1),
        };
        
        assert!(!expired_cached.is_valid());
    }
}
