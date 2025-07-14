// Simple caching and deduplication for TorrentAPI

pub mod cache;
pub mod deduplication;

// Re-export for convenience
pub use cache::{CacheConfig, CacheKey, CacheStats, CachedResult, SearchCache, SharedSearchCache};
pub use deduplication::{DeduplicationConfig, DeduplicationStats, RequestDeduplicator, SharedRequestDeduplicator};
