pub mod cache;
mod client;
// mod deduplication;
mod error;
mod movie_properties;
mod search_options;
mod r#static;
mod torrent;
mod utils;

#[cfg(test)]
mod tests;

use ::utils::surf_logging::SurfLogging;
use cache::{CacheConfig, CacheKey, SearchCache, SharedSearchCache};
use client::bitsearch::BitSearch;
use client::piratebay::PirateBay;
use client::yts::Yts;
pub use client::Provider;
use client::ProviderResponse;
use client::TorrentProvider;
// use deduplication::{DeduplicationConfig, RequestDeduplicator, SharedRequestDeduplicator};
pub use error::Error;
pub use error::ErrorKind;
use futures::future::join_all;
pub use movie_properties::codec::Codec;
pub use movie_properties::quality::Quality;
pub use movie_properties::source::Source;
pub use movie_properties::MovieProperties;
pub use search_options::category::Category;
pub use search_options::invalid_option_error::{InvalidOptionError, SearchOption};
pub use search_options::movie_options::MovieOptions;
pub use search_options::order::Order;
pub use search_options::sort_column::SortColumn;
pub use search_options::SearchOptions;
use std::collections::HashSet;
use std::sync::Arc;
use std::vec;
use surf::Client;
pub use torrent::Torrent;

// Re-export cache types
pub use cache::{CacheStats, CachedResult};
// pub use deduplication::{DeduplicationStats, DeduplicationError};

#[derive(Clone)]
pub struct TorrentClient {
    http: Client,
    cache: Option<SharedSearchCache>,
    // deduplicator: Option<SharedRequestDeduplicator>,
}

impl Default for TorrentClient {
    fn default() -> Self {
        Self::new()
    }
}

impl TorrentClient {
    /// Search all providers with caching and deduplication
    pub async fn search_all(&self, search_options: &SearchOptions) -> Vec<ProviderResponse> {
        self.search(search_options, &Provider::all()).await
    }

    /// Search all providers for movies with caching and deduplication
    pub async fn search_movie_all(&self, movie_options: &MovieOptions) -> Vec<ProviderResponse> {
        self.search_movie(movie_options, &Provider::all()).await
    }

    /// Search specific providers with caching and deduplication
    pub async fn search(
        &self,
        search_options: &SearchOptions,
        providers: &HashSet<Provider>,
    ) -> Vec<ProviderResponse> {
        if search_options.query().is_empty() {
            return vec![];
        }

        let effective_providers = if providers.is_empty() {
            Provider::all()
        } else {
            providers.clone()
        };

        let cache_key = CacheKey::from_search(search_options, &effective_providers);

        // Try cache first
        if let Some(cache) = &self.cache {
            if let Some(cached_result) = cache.get(&cache_key) {
                log::info!("Returning cached search result for query: {}", search_options.query());
                return cached_result;
            }
        }

        // Execute search without deduplication for now
        let result = Self::execute_search_internal(search_options, &effective_providers, &self.http).await;

        // Cache the result
        if let Some(cache) = &self.cache {
            let ttl = cache.config.search_ttl;
            cache.put(cache_key, result.clone(), ttl);
        }

        result
    }

    /// Search specific providers for movies with caching and deduplication
    pub async fn search_movie(
        &self,
        movie_options: &MovieOptions,
        providers: &HashSet<Provider>,
    ) -> Vec<ProviderResponse> {
        if movie_options.imdb().is_empty() {
            return vec![];
        }

        let effective_providers = if providers.is_empty() {
            Provider::all()
        } else {
            providers.clone()
        };

        let cache_key = CacheKey::from_movie_search(movie_options, &effective_providers);

        // Try cache first
        if let Some(cache) = &self.cache {
            if let Some(cached_result) = cache.get(&cache_key) {
                log::info!("Returning cached movie search result for IMDB: {}", movie_options.imdb());
                return cached_result;
            }
        }

        // Execute search without deduplication for now
        let result = Self::execute_movie_search_internal(movie_options, &effective_providers, &self.http).await;

        // Cache the result
        if let Some(cache) = &self.cache {
            let ttl = cache.config.movie_search_ttl;
            cache.put(cache_key, result.clone(), ttl);
        }

        result
    }

    /// Internal method to execute search without caching/deduplication
    async fn execute_search_internal(
        search_options: &SearchOptions,
        providers: &HashSet<Provider>,
        http: &Client,
    ) -> Vec<ProviderResponse> {
        let mut futures = vec![];

        for provider in providers {
            match provider {
                Provider::PirateBay => {
                    futures.push(PirateBay::search_provider(search_options, http))
                }
                Provider::BitSearch => {
                    futures.push(BitSearch::search_provider(search_options, http))
                }
                Provider::Yts => futures.push(Yts::search_provider(search_options, http)),
            }
        }

        join_all(futures).await
    }

    /// Internal method to execute movie search without caching/deduplication
    async fn execute_movie_search_internal(
        movie_options: &MovieOptions,
        providers: &HashSet<Provider>,
        http: &Client,
    ) -> Vec<ProviderResponse> {
        let mut futures = vec![];

        for provider in providers {
            match provider {
                Provider::PirateBay => {
                    futures.push(PirateBay::search_movies_provider(movie_options, http))
                }
                Provider::BitSearch => {
                    futures.push(BitSearch::search_movies_provider(movie_options, http))
                }
                Provider::Yts => {
                    futures.push(Yts::search_movies_provider(movie_options, http))
                }
            }
        }

        join_all(futures).await
    }

    /// Create a new TorrentClient with default settings (no caching/deduplication)
    pub fn new() -> Self {
        Self {
            http: Client::new().with(SurfLogging),
            cache: None,
            // deduplicator: None,
        }
    }

    /// Create a new TorrentClient with caching enabled
    pub fn with_cache(cache_config: CacheConfig) -> Self {
        Self {
            http: Client::new().with(SurfLogging),
            cache: Some(Arc::new(SearchCache::new(cache_config))),
            // deduplicator: None,
        }
    }

    /// Get cache statistics if caching is enabled
    pub fn cache_stats(&self) -> Option<CacheStats> {
        self.cache.as_ref().map(|cache| cache.stats())
    }

    /// Clear cache if caching is enabled
    pub fn clear_cache(&self) {
        if let Some(cache) = &self.cache {
            cache.clear();
        }
    }

    /// Evict expired cache entries if caching is enabled
    pub fn evict_expired_cache(&self) {
        if let Some(cache) = &self.cache {
            cache.evict_expired();
        }
    }
}
