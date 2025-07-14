use crate::cache::{CacheConfig, CacheKey, SearchCache};
use crate::client::ProviderResponse;
use crate::{Category, Order, SearchOptions, SortColumn, TorrentClient};

#[tokio::test]
async fn test_caching_basic() {
    let cache_config = CacheConfig {
        search_ttl: chrono::Duration::minutes(5),
        movie_search_ttl: chrono::Duration::minutes(10),
        max_entries: 100,
        enabled: true,
    };
    
    let client = TorrentClient::with_cache(cache_config);
    
    let search_options = SearchOptions::new(
        "test".to_string(),
        Category::Video,
        SortColumn::Seeders,
        Order::Descending,
    );
    
    // This should work if caching is implemented correctly
    let _results = client.search_all(&search_options).await;
    
    // Check cache stats
    let stats = client.cache_stats();
    assert!(stats.is_some());
}

#[test]
fn test_cache_key_generation() {
    use std::collections::HashSet;
    
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
}
